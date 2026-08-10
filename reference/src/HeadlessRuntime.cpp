#include "HeadlessRuntime.hpp"

#include "BulletManager.hpp"
#include "CanonicalState.hpp"
#include "CanonicalTrace.hpp"
#include "Controller.hpp"
#include "EnemyManager.hpp"
#include "GameManager.hpp"
#include "Gui.hpp"
#include "Player.hpp"
#include "ReplayFile.hpp"
#include "Rng.hpp"
#include "Supervisor.hpp"
#include "ZunEndian.hpp"

#include <SDL2/SDL.h>
#include <cctype>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>

HeadlessRuntime g_HeadlessRuntime;

namespace
{
bool ParseUnsigned(const char *name, const char *value, u64 maxValue, u64 *result)
{
    char *end = NULL;
    errno = 0;
    unsigned long long parsed = std::strtoull(value, &end, 10);
    if (errno != 0 || end == value || *end != '\0' || parsed > maxValue)
    {
        std::fprintf(stderr, "Invalid %s value: %s\n", name, value);
        return false;
    }
    *result = parsed;
    return true;
}

void PrintUsage(const char *program)
{
    std::fprintf(stderr,
                 "Usage: %s [--headless] [--max-ticks N] [--seed N] "
                 "[--practice-stage 1..6] [--difficulty 0..3] [--character 0..1] "
                 "[--shot-type 0..1] [--actions PATH] [--trace PATH] [--canonical-trace PATH] "
                 "[--step] [--auto-shoot] "
                 "[--continue-after-hit]\n"
                 "       %s --headless --replay PATH [--max-ticks N] [--trace PATH] [--canonical-trace PATH]\n"
                 "       %s --replay-info PATH\n"
                 "       %s --canonical-self-test [TRACE-PATH]\n",
                 program,
                 program,
                 program,
                 program);
}

bool ParseAction(const char *name, u16 *mask)
{
    struct NamedAction
    {
        const char *name;
        u16 direction;
    };
    static const NamedAction actions[] = {
        {"stay", 0},
        {"up", TH_BUTTON_UP},
        {"down", TH_BUTTON_DOWN},
        {"left", TH_BUTTON_LEFT},
        {"right", TH_BUTTON_RIGHT},
        {"up_left", TH_BUTTON_UP_LEFT},
        {"up_right", TH_BUTTON_UP_RIGHT},
        {"down_left", TH_BUTTON_DOWN_LEFT},
        {"down_right", TH_BUTTON_DOWN_RIGHT},
    };
    for (const NamedAction &action : actions)
    {
        if (std::strcmp(name, action.name) == 0)
        {
            *mask = action.direction | TH_BUTTON_FOCUS;
            return true;
        }
        char fastName[32];
        std::snprintf(fastName, sizeof(fastName), "%s_fast", action.name);
        if (std::strcmp(name, fastName) == 0)
        {
            *mask = action.direction;
            return true;
        }
    }
    return false;
}

HeadlessPlayerBulletTrace CapturePlayerBullet(const PlayerBullet &bullet)
{
    HeadlessPlayerBulletTrace trace;
    trace.positionBits[0] = bit_cast_from_size(bullet.position.x);
    trace.positionBits[1] = bit_cast_from_size(bullet.position.y);
    trace.positionBits[2] = bit_cast_from_size(bullet.position.z);
    trace.sizeBits[0] = bit_cast_from_size(bullet.size.x);
    trace.sizeBits[1] = bit_cast_from_size(bullet.size.y);
    trace.sizeBits[2] = bit_cast_from_size(bullet.size.z);
    trace.velocityBits[0] = bit_cast_from_size(bullet.velocity.x);
    trace.velocityBits[1] = bit_cast_from_size(bullet.velocity.y);
    trace.unk134Bits[0] = bit_cast_from_size(bullet.unk_134.x);
    trace.unk134Bits[1] = bit_cast_from_size(bullet.unk_134.y);
    trace.unk134Bits[2] = bit_cast_from_size(bullet.unk_134.z);
    trace.spritePositionBits[0] = bit_cast_from_size(bullet.sprite.pos.x);
    trace.spritePositionBits[1] = bit_cast_from_size(bullet.sprite.pos.y);
    trace.spritePositionBits[2] = bit_cast_from_size(bullet.sprite.pos.z);
    if (bullet.sprite.sprite != NULL)
    {
        trace.spriteSizeBits[0] = bit_cast_from_size(bullet.sprite.sprite->widthPx);
        trace.spriteSizeBits[1] = bit_cast_from_size(bullet.sprite.sprite->heightPx);
    }
    trace.sidewaysMotionBits = bit_cast_from_size(bullet.sidewaysMotion);
    trace.timerPrevious = bullet.unk_140.previous;
    trace.timerSubframeBits = bit_cast_from_size(bullet.unk_140.subFrame);
    trace.timerCurrent = bullet.unk_140.current;
    trace.damage = bullet.damage;
    trace.state = bullet.bulletState;
    trace.type = bullet.bulletType;
    trace.unk152 = bullet.unk_152;
    trace.spawnPositionIdx = bullet.spawnPositionIdx;
    trace.spriteTimerPrevious = bullet.sprite.currentTimeInScript.previous;
    trace.spriteTimerSubframeBits = bit_cast_from_size(bullet.sprite.currentTimeInScript.subFrame);
    trace.spriteTimerCurrent = bullet.sprite.currentTimeInScript.current;
    trace.spriteFlags = bit_cast_from_size(bullet.sprite.flags);
    trace.spriteActiveIndex = bullet.sprite.activeSpriteIndex;
    trace.spriteAnmFileIndex = bullet.sprite.anmFileIndex;
    return trace;
}

void WriteU32Vector(FILE *output, const u32 *values, size_t count)
{
    std::fputc('[', output);
    for (size_t index = 0; index < count; index++)
    {
        std::fprintf(output, "%s\"0x%08x\"", index == 0 ? "" : ",", values[index]);
    }
    std::fputc(']', output);
}

void WritePlayerBulletTrace(FILE *output, size_t slot, const HeadlessPlayerBulletTrace &bullet)
{
    std::fprintf(output,
                 "{\"slot\":%zu,\"state\":%d,\"type\":%d,\"damage\":%d,"
                 "\"spawn_position_idx\":%d,\"unk_152\":%d,\"position_bits\":",
                 slot, bullet.state, bullet.type, bullet.damage, bullet.spawnPositionIdx, bullet.unk152);
    WriteU32Vector(output, bullet.positionBits, 3);
    std::fputs(",\"size_bits\":", output);
    WriteU32Vector(output, bullet.sizeBits, 3);
    std::fputs(",\"velocity_bits\":", output);
    WriteU32Vector(output, bullet.velocityBits, 2);
    std::fprintf(output,
                 ",\"sideways_motion_bits\":\"0x%08x\",\"unk_134_bits\":",
                 bullet.sidewaysMotionBits);
    WriteU32Vector(output, bullet.unk134Bits, 3);
    std::fprintf(output,
                 ",\"timer_previous\":%d,\"timer_subframe_bits\":\"0x%08x\","
                 "\"timer_current\":%d,\"sprite_position_bits\":",
                 bullet.timerPrevious, bullet.timerSubframeBits, bullet.timerCurrent);
    WriteU32Vector(output, bullet.spritePositionBits, 3);
    std::fputs(",\"sprite_size_bits\":", output);
    WriteU32Vector(output, bullet.spriteSizeBits, 2);
    std::fprintf(output,
                 ",\"sprite_timer_previous\":%d,\"sprite_timer_subframe_bits\":\"0x%08x\","
                 "\"sprite_timer_current\":%d,\"sprite_flags\":%u,"
                 "\"sprite_active_index\":%d,\"sprite_anm_file_index\":%d}",
                 bullet.spriteTimerPrevious, bullet.spriteTimerSubframeBits, bullet.spriteTimerCurrent,
                 bullet.spriteFlags, bullet.spriteActiveIndex, bullet.spriteAnmFileIndex);
}

void WritePlayerSpawnSide(FILE *output, const HeadlessPlayerBulletTrace (&bullets)[80])
{
    std::fputs("{\"slot_states\":[", output);
    for (size_t slot = 0; slot < 80; slot++)
    {
        std::fprintf(output, "%s%d", slot == 0 ? "" : ",", bullets[slot].state);
    }
    std::fputs("],\"active_slots\":[", output);
    bool first = true;
    for (size_t slot = 0; slot < 80; slot++)
    {
        if (bullets[slot].state == BULLET_STATE_UNUSED)
        {
            continue;
        }
        std::fputs(first ? "" : ",", output);
        WritePlayerBulletTrace(output, slot, bullets[slot]);
        first = false;
    }
    std::fputs("],\"slot_carry\":[", output);
    for (size_t slot = 0; slot < 80; slot++)
    {
        const HeadlessPlayerBulletTrace &bullet = bullets[slot];
        std::fprintf(output,
                     "%s{\"sideways_motion_bits\":\"0x%08x\","
                     "\"unk_134_x_bits\":\"0x%08x\",\"unk_152\":%d,"
                     "\"spawn_position_idx\":%d}",
                     slot == 0 ? "" : ",", bullet.sidewaysMotionBits, bullet.unk134Bits[0],
                     bullet.unk152, bullet.spawnPositionIdx);
    }
    std::fputs("]}", output);
}

void WritePlayerSpawnTrace(FILE *output, const HeadlessPlayerSpawnTrace &trace)
{
    if (!trace.valid)
    {
        std::fputs("null", output);
        return;
    }
    if (!trace.returned)
    {
        std::fputs("{\"error\":\"SpawnBullets did not return\"}", output);
        return;
    }
    std::fprintf(output, "{\"timer\":%u,\"current_power\":%u,\"is_focus\":%u,"
                         "\"player_position_bits\":",
                 trace.timer, trace.currentPower, trace.isFocus);
    WriteU32Vector(output, trace.playerPositionBits, 3);
    std::fputs(",\"orb_position_bits\":[", output);
    WriteU32Vector(output, trace.orbPositionBits[0], 3);
    std::fputc(',', output);
    WriteU32Vector(output, trace.orbPositionBits[1], 3);
    std::fputs("],\"before\":", output);
    WritePlayerSpawnSide(output, trace.before);
    std::fputs(",\"after\":", output);
    WritePlayerSpawnSide(output, trace.after);
    std::fputc('}', output);
}

void WriteLivePlayerBullets(FILE *output, const Player &player)
{
    HeadlessPlayerBulletTrace bullets[80];
    for (size_t slot = 0; slot < 80; slot++)
    {
        bullets[slot] = CapturePlayerBullet(player.bullets[slot]);
    }
    WritePlayerSpawnSide(output, bullets);
}

void WritePlayerBulletUpdateTrace(FILE *output, const HeadlessPlayerBulletUpdateTrace &trace)
{
    if (!trace.valid)
    {
        std::fputs("null", output);
        return;
    }
    if (!trace.returned)
    {
        std::fputs("{\"error\":\"UpdatePlayerBullets did not return\"}", output);
        return;
    }
    std::fputs("{\"last_enemy_hit_bits\":", output);
    WriteU32Vector(output, trace.lastEnemyHitBits, 3);
    std::fputs(",\"before\":", output);
    WritePlayerSpawnSide(output, trace.before);
    std::fputs(",\"after\":", output);
    WritePlayerSpawnSide(output, trace.after);
    std::fputc('}', output);
}

void WritePlayerDamageTrace(FILE *output, const HeadlessPlayerDamageTrace &trace)
{
    if (!trace.returned)
    {
        std::fputs("{\"error\":\"CalcDamageToEnemy did not return\"}", output);
        return;
    }
    std::fputs("{\"enemy_position_bits\":", output);
    WriteU32Vector(output, trace.enemyPositionBits, 3);
    std::fputs(",\"enemy_hitbox_bits\":", output);
    WriteU32Vector(output, trace.enemyHitboxBits, 3);
    std::fprintf(output,
                 ",\"bomb_is_in_use\":%u,\"damage\":%d,\"hit_with_laser_during_bomb\":%s,\"before\":",
                 trace.bombIsInUse, trace.damage, trace.hitWithLaserDuringBomb ? "true" : "false");
    WritePlayerSpawnSide(output, trace.before);
    std::fputs(",\"after\":", output);
    WritePlayerSpawnSide(output, trace.after);
    std::fputc('}', output);
}
} // namespace

void HeadlessRuntime::BeginPlayerSpawnTrace(const Player *player, u32 timer)
{
    this->playerSpawnTrace = {};
    if (!this->enabled || this->traceFile == NULL)
    {
        return;
    }
    HeadlessPlayerSpawnTrace &trace = this->playerSpawnTrace;
    trace.valid = true;
    trace.timer = timer;
    trace.currentPower = g_GameManager.currentPower;
    trace.isFocus = player->isFocus;
    trace.playerPositionBits[0] = bit_cast_from_size(player->positionCenter.x);
    trace.playerPositionBits[1] = bit_cast_from_size(player->positionCenter.y);
    trace.playerPositionBits[2] = bit_cast_from_size(player->positionCenter.z);
    trace.orbPositionBits[0][0] = bit_cast_from_size(player->orbsPosition[0].x);
    trace.orbPositionBits[0][1] = bit_cast_from_size(player->orbsPosition[0].y);
    trace.orbPositionBits[0][2] = bit_cast_from_size(player->orbsPosition[0].z);
    trace.orbPositionBits[1][0] = bit_cast_from_size(player->orbsPosition[1].x);
    trace.orbPositionBits[1][1] = bit_cast_from_size(player->orbsPosition[1].y);
    trace.orbPositionBits[1][2] = bit_cast_from_size(player->orbsPosition[1].z);
    for (size_t slot = 0; slot < 80; slot++)
    {
        trace.before[slot] = CapturePlayerBullet(player->bullets[slot]);
    }
}

void HeadlessRuntime::EndPlayerSpawnTrace(const Player *player)
{
    HeadlessPlayerSpawnTrace &trace = this->playerSpawnTrace;
    if (!trace.valid)
    {
        return;
    }
    for (size_t slot = 0; slot < 80; slot++)
    {
        trace.after[slot] = CapturePlayerBullet(player->bullets[slot]);
    }
    trace.returned = true;
}

void HeadlessRuntime::BeginPlayerBulletUpdateTrace(const Player *player)
{
    this->playerBulletUpdateTrace = {};
    if (!this->enabled || this->traceFile == NULL)
    {
        return;
    }
    HeadlessPlayerBulletUpdateTrace &trace = this->playerBulletUpdateTrace;
    trace.valid = true;
    trace.lastEnemyHitBits[0] = bit_cast_from_size(player->positionOfLastEnemyHit.x);
    trace.lastEnemyHitBits[1] = bit_cast_from_size(player->positionOfLastEnemyHit.y);
    trace.lastEnemyHitBits[2] = bit_cast_from_size(player->positionOfLastEnemyHit.z);
    for (size_t slot = 0; slot < 80; slot++)
    {
        trace.before[slot] = CapturePlayerBullet(player->bullets[slot]);
    }
}

void HeadlessRuntime::EndPlayerBulletUpdateTrace(const Player *player)
{
    HeadlessPlayerBulletUpdateTrace &trace = this->playerBulletUpdateTrace;
    if (!trace.valid)
    {
        return;
    }
    for (size_t slot = 0; slot < 80; slot++)
    {
        trace.after[slot] = CapturePlayerBullet(player->bullets[slot]);
    }
    trace.returned = true;
}

void HeadlessRuntime::BeginPlayerDamageTrace(const Player *player, const ZunVec3 *enemyPosition,
                                             const ZunVec3 *enemyHitbox)
{
    if (!this->enabled || this->traceFile == NULL)
    {
        return;
    }
    if (this->playerDamageTraceCount >= HEADLESS_PLAYER_DAMAGE_TRACE_CAPACITY)
    {
        this->playerDamageTraceOverflow = true;
        return;
    }
    HeadlessPlayerDamageTrace &trace = this->playerDamageTraces[this->playerDamageTraceCount++];
    trace = {};
    trace.enemyPositionBits[0] = bit_cast_from_size(enemyPosition->x);
    trace.enemyPositionBits[1] = bit_cast_from_size(enemyPosition->y);
    trace.enemyPositionBits[2] = bit_cast_from_size(enemyPosition->z);
    trace.enemyHitboxBits[0] = bit_cast_from_size(enemyHitbox->x);
    trace.enemyHitboxBits[1] = bit_cast_from_size(enemyHitbox->y);
    trace.enemyHitboxBits[2] = bit_cast_from_size(enemyHitbox->z);
    trace.bombIsInUse = player->bombInfo.isInUse;
    for (size_t slot = 0; slot < 80; slot++)
    {
        trace.before[slot] = CapturePlayerBullet(player->bullets[slot]);
    }
}

void HeadlessRuntime::EndPlayerDamageTrace(const Player *player, i32 damage, bool hitWithLaserDuringBomb)
{
    if (!this->enabled || this->traceFile == NULL || this->playerDamageTraceOverflow)
    {
        return;
    }
    if (this->playerDamageTraceCount == 0)
    {
        this->playerDamageTraceOverflow = true;
        return;
    }
    HeadlessPlayerDamageTrace &trace = this->playerDamageTraces[this->playerDamageTraceCount - 1];
    if (trace.returned)
    {
        this->playerDamageTraceOverflow = true;
        return;
    }
    trace.damage = damage;
    trace.hitWithLaserDuringBomb = hitWithLaserDuringBomb;
    for (size_t slot = 0; slot < 80; slot++)
    {
        trace.after[slot] = CapturePlayerBullet(player->bullets[slot]);
    }
    trace.returned = true;
}

bool HeadlessRuntime::ParseArguments(int argc, char *argv[])
{
    for (int i = 1; i < argc; i++)
    {
        if (std::strcmp(argv[i], "--headless") == 0)
        {
            this->enabled = true;
        }
        else if (std::strcmp(argv[i], "--max-ticks") == 0)
        {
            u64 parsed;
            if (++i >= argc || !ParseUnsigned("--max-ticks", argv[i], std::numeric_limits<u64>::max(), &parsed))
            {
                PrintUsage(argv[0]);
                return false;
            }
            this->maxTicks = parsed;
        }
        else if (std::strcmp(argv[i], "--seed") == 0)
        {
            u64 parsed;
            if (++i >= argc || !ParseUnsigned("--seed", argv[i], std::numeric_limits<u16>::max(), &parsed))
            {
                PrintUsage(argv[0]);
                return false;
            }
            this->seed = (u16)parsed;
            this->seedProvided = true;
        }
        else if (std::strcmp(argv[i], "--practice-stage") == 0)
        {
            u64 parsed;
            if (++i >= argc || !ParseUnsigned("--practice-stage", argv[i], 6, &parsed) || parsed == 0)
            {
                PrintUsage(argv[0]);
                return false;
            }
            this->practiceStage = (i32)parsed;
        }
        else if (std::strcmp(argv[i], "--difficulty") == 0)
        {
            u64 parsed;
            if (++i >= argc || !ParseUnsigned("--difficulty", argv[i], 3, &parsed))
            {
                PrintUsage(argv[0]);
                return false;
            }
            this->difficulty = (i32)parsed;
        }
        else if (std::strcmp(argv[i], "--character") == 0)
        {
            u64 parsed;
            if (++i >= argc || !ParseUnsigned("--character", argv[i], 1, &parsed))
            {
                PrintUsage(argv[0]);
                return false;
            }
            this->character = (i32)parsed;
        }
        else if (std::strcmp(argv[i], "--shot-type") == 0)
        {
            u64 parsed;
            if (++i >= argc || !ParseUnsigned("--shot-type", argv[i], 1, &parsed))
            {
                PrintUsage(argv[0]);
                return false;
            }
            this->shotType = (i32)parsed;
        }
        else if (std::strcmp(argv[i], "--actions") == 0)
        {
            if (++i >= argc)
            {
                PrintUsage(argv[0]);
                return false;
            }
            this->actionsPath = argv[i];
        }
        else if (std::strcmp(argv[i], "--trace") == 0)
        {
            if (++i >= argc)
            {
                PrintUsage(argv[0]);
                return false;
            }
            this->tracePath = argv[i];
        }
        else if (std::strcmp(argv[i], "--canonical-trace") == 0)
        {
            if (++i >= argc)
            {
                PrintUsage(argv[0]);
                return false;
            }
            this->canonicalTracePath = argv[i];
        }
        else if (std::strcmp(argv[i], "--replay-info") == 0)
        {
            if (++i >= argc)
            {
                PrintUsage(argv[0]);
                return false;
            }
            this->replayInfoPath = argv[i];
        }
        else if (std::strcmp(argv[i], "--replay") == 0)
        {
            if (++i >= argc)
            {
                PrintUsage(argv[0]);
                return false;
            }
            this->replayPath = argv[i];
        }
        else if (std::strcmp(argv[i], "--auto-shoot") == 0)
        {
            this->autoShoot = true;
        }
        else if (std::strcmp(argv[i], "--step") == 0)
        {
            this->stepMode = true;
        }
        else if (std::strcmp(argv[i], "--continue-after-hit") == 0)
        {
            this->continueAfterHit = true;
        }
        else if (std::strcmp(argv[i], "--canonical-self-test") == 0)
        {
            this->canonicalSelfTest = true;
            if (i + 1 < argc && std::strncmp(argv[i + 1], "--", 2) != 0)
            {
                this->canonicalSelfTestPath = argv[++i];
            }
        }
        else if (std::strcmp(argv[i], "--help") == 0)
        {
            PrintUsage(argv[0]);
            return false;
        }
        else
        {
            std::fprintf(stderr, "Unknown argument: %s\n", argv[i]);
            PrintUsage(argv[0]);
            return false;
        }
    }

    if (this->canonicalSelfTest)
    {
        const int expectedArguments = this->canonicalSelfTestPath == NULL ? 2 : 3;
        if (argc != expectedArguments)
        {
            std::fprintf(stderr, "--canonical-self-test cannot be combined with other options\n");
            return false;
        }
        return true;
    }

    if (this->replayInfoPath != NULL)
    {
        if (this->enabled || this->maxTicks != 0 || this->seedProvided || this->practiceStage != 0 ||
            this->actionsPath != NULL || this->tracePath != NULL || this->canonicalTracePath != NULL ||
            this->autoShoot || this->stepMode || this->continueAfterHit)
        {
            std::fprintf(stderr, "--replay-info cannot be combined with runtime options\n");
            return false;
        }
        return true;
    }
    if (this->replayPath != NULL)
    {
        if (!this->enabled)
        {
            std::fprintf(stderr, "--replay requires --headless\n");
            return false;
        }
        if (this->practiceStage != 0 || this->actionsPath != NULL || this->stepMode || this->autoShoot ||
            this->continueAfterHit || this->seedProvided)
        {
            std::fprintf(stderr,
                         "--replay cannot be combined with Practice, action, step, seed, auto-shoot, or hit options\n");
            return false;
        }
    }
    if (!this->enabled &&
        (this->maxTicks != 0 || this->seedProvided || this->practiceStage != 0 || this->actionsPath != NULL ||
         this->tracePath != NULL || this->canonicalTracePath != NULL || this->autoShoot || this->stepMode ||
         this->continueAfterHit || this->replayPath != NULL))
    {
        std::fprintf(stderr, "headless-only runtime options require --headless\n");
        return false;
    }
    if (this->actionsPath != NULL && this->practiceStage == 0)
    {
        std::fprintf(stderr, "--actions requires --practice-stage\n");
        return false;
    }
    if (this->stepMode && this->practiceStage == 0)
    {
        std::fprintf(stderr, "--step requires --practice-stage\n");
        return false;
    }
    if (this->stepMode &&
        (this->actionsPath != NULL || this->tracePath != NULL || this->canonicalTracePath != NULL))
    {
        std::fprintf(stderr, "--step cannot be combined with file-based action or trace options\n");
        return false;
    }
    if (this->tracePath != NULL && this->canonicalTracePath != NULL &&
        std::strcmp(this->tracePath, this->canonicalTracePath) == 0)
    {
        std::fprintf(stderr, "--trace and --canonical-trace require different paths\n");
        return false;
    }
    return true;
}

bool HeadlessRuntime::RunCanonicalSelfTest() const
{
    if (!CanonicalTrace::SelfTest())
    {
        std::fprintf(stderr, "Canonical trace self-test failed\n");
        return false;
    }
    if (this->canonicalSelfTestPath != NULL)
    {
        char error[256];
        if (!CanonicalTrace::WriteTestFixture(this->canonicalSelfTestPath, error, sizeof(error)))
        {
            std::fprintf(stderr, "Canonical trace fixture failed: %s\n", error);
            return false;
        }
    }
    const Sha256Digest schemaDigest = CanonicalTrace::SchemaDigest();
    std::printf("canonical trace self-test passed; schema_sha256=");
    for (u8 byte : schemaDigest)
    {
        std::printf("%02x", byte);
    }
    std::printf("; record_size=%zu\n", CANONICAL_TRACE_RECORD_SIZE);
    return true;
}

bool HeadlessRuntime::PrintReplayInfo() const
{
    ReplayFile replay;
    char error[256];
    if (!replay.LoadExternal(this->replayInfoPath, error, sizeof(error)))
    {
        std::fprintf(stderr, "Invalid TH06 replay: %s\n", error);
        return false;
    }

    const ReplayHeader *header = replay.Header();
    std::printf("{\"valid\":true,\"size\":%zu,\"version\":%u,\"shot_type_character\":%u,"
                "\"difficulty\":%u,\"score\":%d,\"stages\":[",
                replay.Size(), static_cast<unsigned>(header->version),
                static_cast<unsigned>(header->shottypeChara), static_cast<unsigned>(header->difficulty),
                header->score);
    bool first = true;
    for (size_t index = 0; index < 7; index++)
    {
        const ReplayStageView &stage = replay.Stage(index);
        if (stage.data == NULL)
        {
            continue;
        }
        std::printf("%s{\"stage\":%zu,\"offset\":%zu,\"size\":%zu,\"records\":%zu,"
                    "\"playback_records\":%zu,\"terminal_frame\":%d}",
                    first ? "" : ",", index + 1, stage.fileOffset, stage.byteSize, stage.inputRecordCount,
                    stage.playbackRecordCount, stage.terminalFrame);
        first = false;
    }
    std::printf("]}\n");
    return true;
}

bool HeadlessRuntime::PrepareReplay()
{
    if (this->replayPath == NULL)
    {
        return true;
    }
    if (std::strlen(this->replayPath) >= sizeof(g_GameManager.replayFile))
    {
        std::fprintf(stderr, "Replay path is too long for TH06: %s\n", this->replayPath);
        return false;
    }

    ReplayFile replay;
    char error[256];
    if (!replay.LoadExternal(this->replayPath, error, sizeof(error)))
    {
        std::fprintf(stderr, "Invalid TH06 replay: %s\n", error);
        return false;
    }

    const ReplayHeader *header = replay.Header();
    this->difficulty = header->difficulty;
    this->character = header->shottypeChara / 2;
    this->shotType = header->shottypeChara % 2;
    for (size_t index = 0; index < 7; index++)
    {
        const ReplayStageView &stage = replay.Stage(index);
        if (stage.data == NULL)
        {
            continue;
        }
        this->replayStartStage = static_cast<i32>(index + 1);
        this->replayInitialLives = stage.data->livesRemaining;
        this->replayInitialBombs = stage.data->bombsRemaining;
        this->seed = static_cast<u16>(stage.data->randomSeed);
        this->seedProvided = true;
        break;
    }
    if (this->replayStartStage == 0)
    {
        std::fprintf(stderr, "Replay has no playable stage\n");
        return false;
    }
    return true;
}

void HeadlessRuntime::ConfigureEnvironment() const
{
    if (!this->enabled)
    {
        return;
    }
    // Headless mode is a runtime contract, so stale launcher environment must
    // not silently select a display or audio device.
    SDL_setenv("SDL_VIDEODRIVER", "dummy", 1);
    SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);
    std::fprintf(stderr, "TH06 headless logic mode enabled (max_ticks=%llu, seed=%s)\n",
                 (unsigned long long)this->maxTicks, this->seedProvided ? "fixed" : "wall-clock");
}

bool HeadlessRuntime::InitializeIo()
{
    if (!this->PrepareReplay())
    {
        return false;
    }
    if (this->stepMode)
    {
        this->actionsFile = stdin;
        this->traceFile = stdout;
    }
    else if (this->actionsPath != NULL)
    {
        this->actionsFile = std::fopen(this->actionsPath, "r");
        if (this->actionsFile == NULL)
        {
            std::perror(this->actionsPath);
            return false;
        }
        this->ownsActionsFile = true;
    }
    if (this->tracePath != NULL)
    {
        this->traceFile = std::fopen(this->tracePath, "w");
        if (this->traceFile == NULL)
        {
            std::perror(this->tracePath);
            CloseIo();
            return false;
        }
        this->ownsTraceFile = true;
    }
    if (this->canonicalTracePath != NULL)
    {
        this->canonicalTraceFile = std::fopen(this->canonicalTracePath, "wb");
        if (this->canonicalTraceFile == NULL)
        {
            std::perror(this->canonicalTracePath);
            CloseIo();
            return false;
        }
        this->ownsCanonicalTraceFile = true;
    }
    return true;
}

void HeadlessRuntime::CloseIo()
{
    if (this->actionsFile != NULL && this->ownsActionsFile)
    {
        std::fclose(this->actionsFile);
        this->actionsFile = NULL;
    }
    if (this->traceFile != NULL && this->ownsTraceFile)
    {
        std::fclose(this->traceFile);
        this->traceFile = NULL;
    }
    if (this->canonicalTraceFile != NULL && this->ownsCanonicalTraceFile)
    {
        if (std::fclose(this->canonicalTraceFile) != 0)
        {
            std::perror(this->canonicalTracePath);
            this->outputError = true;
        }
        this->canonicalTraceFile = NULL;
    }
    this->actionsFile = NULL;
    this->traceFile = NULL;
    this->canonicalTraceFile = NULL;
    this->ownsActionsFile = false;
    this->ownsTraceFile = false;
    this->ownsCanonicalTraceFile = false;
}

void HeadlessRuntime::ConfigureDirectPractice()
{
    if (this->practiceStage == 0)
    {
        return;
    }
    g_GameManager.isInPracticeMode = 1;
    g_GameManager.difficulty = (Difficulty)this->difficulty;
    g_GameManager.character = (u8)this->character;
    g_GameManager.shotType = (u8)this->shotType;
    g_GameManager.currentStage = this->practiceStage - 1;
    g_GameManager.livesRemaining = 2;
    g_GameManager.bombsRemaining = 3;
    g_GameManager.isInReplay = 0;
    g_GameManager.demoMode = 0;

    // Reproduce the generic state transition made after Practice selection,
    // without driving or depending on the title menu.
    g_Supervisor.wantedState = SUPERVISOR_STATE_MAINMENU;
    g_Supervisor.curState = SUPERVISOR_STATE_GAMEMANAGER;
}

void HeadlessRuntime::ConfigureDirectReplay()
{
    if (this->replayPath == NULL)
    {
        return;
    }
    g_GameManager.isInPracticeMode = 0;
    g_GameManager.difficulty = static_cast<Difficulty>(this->difficulty);
    g_GameManager.character = static_cast<u8>(this->character);
    g_GameManager.shotType = static_cast<u8>(this->shotType);
    g_GameManager.currentStage = this->replayStartStage - 1;
    g_GameManager.livesRemaining = this->replayInitialLives;
    g_GameManager.bombsRemaining = this->replayInitialBombs;
    g_GameManager.isInReplay = 1;
    g_GameManager.demoMode = 0;
    std::snprintf(reinterpret_cast<char *>(g_GameManager.replayFile), sizeof(g_GameManager.replayFile), "%s",
                  this->replayPath);

    // Reproduce the state transition made by replay selection without driving
    // the title menu. ReplayManager still injects inputs at calc priority 5.
    g_Supervisor.wantedState = SUPERVISOR_STATE_MAINMENU;
    g_Supervisor.curState = SUPERVISOR_STATE_GAMEMANAGER;
}

u16 HeadlessRuntime::NextInput()
{
    if (!this->enabled)
    {
        return 0;
    }
    if (!this->inputReady)
    {
        return 0;
    }
    if (this->replayPath != NULL)
    {
        // ReplayManager replaces captured gameplay bits later in the authentic
        // calc-chain position. Host input must contribute no uncaptured bits.
        return 0;
    }
    if (this->actionsFile == NULL)
    {
        return this->autoShoot ? TH_BUTTON_SHOOT : 0;
    }
    while (this->actionRepeatsRemaining == 0)
    {
        char line[256];
        if (std::fgets(line, sizeof(line), this->actionsFile) == NULL)
        {
            std::fprintf(stderr, "Headless action stream exhausted at tick %llu\n", (unsigned long long)this->ticks);
            this->inputError = true;
            return 0;
        }
        char *cursor = line;
        while (std::isspace((unsigned char)*cursor))
        {
            cursor++;
        }
        if (*cursor == '\0' || *cursor == '#')
        {
            continue;
        }
        unsigned long long repeats = 1;
        char action[64];
        char extra;
        int parsed = std::sscanf(cursor, "%llu %63s %c", &repeats, action, &extra);
        if (parsed == 2 && repeats != 0)
        {
            // Parsed the run-length form.
        }
        else if (std::sscanf(cursor, "%63s %c", action, &extra) == 1)
        {
            repeats = 1;
        }
        else
        {
            std::fprintf(stderr, "Invalid headless action line: %s", line);
            this->inputError = true;
            return 0;
        }
        if (!ParseAction(action, &this->repeatedAction))
        {
            std::fprintf(stderr, "Unknown or forbidden headless action: %s\n", action);
            this->inputError = true;
            return 0;
        }
        this->actionRepeatsRemaining = repeats;
    }
    this->actionRepeatsRemaining--;
    u16 result = this->repeatedAction | (this->autoShoot ? TH_BUTTON_SHOOT : 0);
    if ((result & TH_BUTTON_BOMB) != 0)
    {
        std::fprintf(stderr, "Headless input contract attempted Bomb\n");
        this->inputError = true;
        return 0;
    }
    return result;
}

bool HeadlessRuntime::ShouldStopForHit() const
{
    return this->replayPath == NULL && this->inputReady && !this->continueAfterHit &&
           g_Player.playerState == PLAYER_STATE_DEAD;
}

bool HeadlessRuntime::IsReplayComplete() const
{
    return this->replayPath != NULL && g_Supervisor.curState == SUPERVISOR_STATE_MAINMENU_REPLAY;
}

bool HeadlessRuntime::WriteCanonicalState(const char *terminalReason)
{
    if (this->canonicalTraceFile == NULL)
    {
        return true;
    }

    char error[256];
    if (!this->canonicalHeaderWritten)
    {
        CanonicalRunConfig config;
        config.initialSeed = this->actualSeed;
        config.difficulty = static_cast<u8>(this->difficulty);
        config.character = static_cast<u8>(this->character);
        config.shotType = static_cast<u8>(this->shotType);
        config.startStage = static_cast<u8>(this->replayPath != NULL ? this->replayStartStage : this->practiceStage);
        config.mode = this->replayPath != NULL ? CanonicalRunMode::REPLAY
                                              : this->practiceStage != 0 ? CanonicalRunMode::PRACTICE
                                                                         : CanonicalRunMode::UNKNOWN;
        if (!CanonicalTrace::WriteHeader(this->canonicalTraceFile, config, error, sizeof(error)))
        {
            std::fprintf(stderr, "Canonical trace header failed: %s\n", error);
            return false;
        }
        this->canonicalHeaderWritten = true;
    }
    if (!this->inputReady)
    {
        return true;
    }

    CanonicalFrameMetadata frame;
    frame.tick = this->ticks;
    frame.gameFrame = g_GameManager.gameFrames;
    frame.stage = g_GameManager.currentStage;
    frame.input = g_CurFrameInput;
    frame.terminalReason = CanonicalTrace::ParseTerminalReason(terminalReason);
    frame.flags = 1;
    if (this->replayPath != NULL)
    {
        frame.flags |= 1 << 1;
    }
    if (this->practiceStage != 0)
    {
        frame.flags |= 1 << 2;
    }
    if (g_GameManager.isTimeStopped)
    {
        frame.flags |= 1 << 3;
    }
    frame.supervisorState = g_Supervisor.curState;
    frame.recordIndex = this->canonicalRecords;

    const CanonicalSubsystemDigests subsystems = CanonicalState::Capture();
    if (!CanonicalTrace::WriteRecord(this->canonicalTraceFile, frame, subsystems, error, sizeof(error)))
    {
        std::fprintf(stderr, "Canonical trace record failed at index %llu: %s\n",
                     static_cast<unsigned long long>(this->canonicalRecords), error);
        return false;
    }
    this->canonicalRecords++;
    if (terminalReason != NULL && std::fflush(this->canonicalTraceFile) != 0)
    {
        std::perror(this->canonicalTracePath);
        return false;
    }
    return true;
}

void HeadlessRuntime::WriteState(const char *terminalReason)
{
    this->terminalReason = terminalReason;
    if (this->practiceStage != 0 && g_GameManager.currentStage == this->practiceStage)
    {
        this->inputReady = true;
    }
    if (this->replayPath != NULL && g_GameManager.currentStage >= this->replayStartStage)
    {
        this->inputReady = true;
    }
    if (!this->WriteCanonicalState(terminalReason))
    {
        this->outputError = true;
    }
    if (this->traceFile == NULL)
    {
        return;
    }
    char terminalJson[64];
    if (terminalReason == NULL)
    {
        std::snprintf(terminalJson, sizeof(terminalJson), "null");
    }
    else
    {
        std::snprintf(terminalJson, sizeof(terminalJson), "\"%s\"", terminalReason);
    }
    std::fprintf(this->traceFile,
                 "{\"tick\":%llu,\"terminal_reason\":%s,"
                 "\"scope\":{\"difficulty\":%d,\"character\":%d,\"shot_type\":%d,\"stage\":%d},"
                 "\"initial_seed\":%u,\"supervisor_state\":%d,\"stage\":%d,\"game_frame\":%u,"
                 "\"rng_seed\":%u,\"rng_generation\":%u,\"input\":%u,"
                 "\"is_time_stopped\":%d,\"gui_has_current_message\":%d,"
                 "\"effective_rate_bits\":%u,"
                 "\"framerate_multiplier_bits\":%u,"
                 "\"movement_min_x_bits\":%u,\"movement_min_y_bits\":%u,"
                 "\"movement_size_x_bits\":%u,\"movement_size_y_bits\":%u,"
                 "\"player\":{\"x\":%.9g,\"y\":%.9g,\"z\":%.9g,"
                 "\"x_bits\":%u,\"y_bits\":%u,\"z_bits\":%u,\"state\":%d,"
                 "\"respawn_timer\":%d,\"bomb_is_in_use\":%u,"
                 "\"invulnerability_timer_previous\":%d,"
                 "\"invulnerability_timer_subframe_bits\":%u,"
                 "\"invulnerability_timer_current\":%d,"
                 "\"is_focus\":%d,\"previous_frame_input\":%d,"
                 "\"fire_bullet_timer_previous\":%d,"
                 "\"fire_bullet_timer_subframe_bits\":%u,"
                 "\"fire_bullet_timer_current\":%d,"
                 "\"horizontal_multiplier_bits\":%u,\"vertical_multiplier_bits\":%u,"
                 "\"orthogonal_speed_bits\":%u,\"orthogonal_focus_speed_bits\":%u,"
                 "\"diagonal_speed_bits\":%u,\"diagonal_focus_speed_bits\":%u},"
                 "\"lives\":%d,\"bombs\":%d,\"score\":%u,"
                 "\"deaths\":%d,\"bombs_used\":%d,\"num_retries\":%u,"
                 "\"current_power\":%u,\"rank\":%d,\"subrank\":%d,\"player_spawn\":",
                 (unsigned long long)this->ticks, terminalJson,
                 this->difficulty, this->character, this->shotType,
                 this->replayPath == NULL ? this->practiceStage : g_GameManager.currentStage, this->actualSeed,
                 g_Supervisor.curState, g_GameManager.currentStage,
                 g_GameManager.gameFrames, g_Rng.seed, g_Rng.generationCount, g_CurFrameInput,
                 g_GameManager.isTimeStopped, g_Gui.HasCurrentMsgIdx(),
                 bit_cast_from_size(g_Supervisor.effectiveFramerateMultiplier),
                 bit_cast_from_size(g_Supervisor.framerateMultiplier),
                 bit_cast_from_size(g_GameManager.playerMovementAreaTopLeftPos.x),
                 bit_cast_from_size(g_GameManager.playerMovementAreaTopLeftPos.y),
                 bit_cast_from_size(g_GameManager.playerMovementAreaSize.x),
                 bit_cast_from_size(g_GameManager.playerMovementAreaSize.y),
                 g_Player.positionCenter.x, g_Player.positionCenter.y, g_Player.positionCenter.z,
                 bit_cast_from_size(g_Player.positionCenter.x), bit_cast_from_size(g_Player.positionCenter.y),
                 bit_cast_from_size(g_Player.positionCenter.z), g_Player.playerState,
                 g_Player.respawnTimer, g_Player.bombInfo.isInUse,
                 g_Player.invulnerabilityTimer.previous,
                 bit_cast_from_size(g_Player.invulnerabilityTimer.subFrame),
                 g_Player.invulnerabilityTimer.current,
                 g_Player.isFocus, g_Player.previousFrameInput,
                 g_Player.fireBulletTimer.previous,
                 bit_cast_from_size(g_Player.fireBulletTimer.subFrame),
                 g_Player.fireBulletTimer.current,
                 bit_cast_from_size(g_Player.horizontalMovementSpeedMultiplierDuringBomb),
                 bit_cast_from_size(g_Player.verticalMovementSpeedMultiplierDuringBomb),
                 bit_cast_from_size(g_Player.characterData.orthogonalMovementSpeed),
                 bit_cast_from_size(g_Player.characterData.orthogonalMovementSpeedFocus),
                 bit_cast_from_size(g_Player.characterData.diagonalMovementSpeed),
                 bit_cast_from_size(g_Player.characterData.diagonalMovementSpeedFocus),
                 g_GameManager.livesRemaining, g_GameManager.bombsRemaining, g_GameManager.score,
                 g_GameManager.deaths, g_GameManager.bombsUsed, g_GameManager.numRetries,
                 g_GameManager.currentPower, g_GameManager.rank, g_GameManager.subRank);
    WritePlayerSpawnTrace(this->traceFile, this->playerSpawnTrace);
    std::fputs(",\"player_bullet_update\":", this->traceFile);
    WritePlayerBulletUpdateTrace(this->traceFile, this->playerBulletUpdateTrace);
    std::fprintf(this->traceFile,
                 ",\"player_last_enemy_hit_bits\":[\"0x%08x\",\"0x%08x\",\"0x%08x\"]",
                 bit_cast_from_size(g_Player.positionOfLastEnemyHit.x),
                 bit_cast_from_size(g_Player.positionOfLastEnemyHit.y),
                 bit_cast_from_size(g_Player.positionOfLastEnemyHit.z));
    std::fputs(",\"player_bullets_frame\":", this->traceFile);
    WriteLivePlayerBullets(this->traceFile, g_Player);
    std::fputs(",\"player_damage_calls\":[", this->traceFile);
    for (size_t index = 0; index < this->playerDamageTraceCount; index++)
    {
        std::fputs(index == 0 ? "" : ",", this->traceFile);
        WritePlayerDamageTrace(this->traceFile, this->playerDamageTraces[index]);
    }
    std::fprintf(this->traceFile, "],\"player_damage_trace_overflow\":%s",
                 this->playerDamageTraceOverflow ? "true" : "false");
    std::fputs(",\"bullets\":[", this->traceFile);
    bool first = true;
    for (const Bullet &bullet : g_BulletManager.bullets)
    {
        if (bullet.state == 0)
        {
            continue;
        }
        std::fprintf(this->traceFile, "%s{\"x\":%.9g,\"y\":%.9g,\"vx\":%.9g,\"vy\":%.9g,\"state\":%u}",
                     first ? "" : ",", bullet.pos.x, bullet.pos.y, bullet.velocity.x, bullet.velocity.y,
                     bullet.state);
        first = false;
    }
    std::fprintf(this->traceFile, "],\"lasers\":[");
    first = true;
    for (const Laser &laser : g_BulletManager.lasers)
    {
        if (!laser.inUse)
        {
            continue;
        }
        std::fprintf(this->traceFile,
                     "%s{\"x\":%.9g,\"y\":%.9g,\"angle\":%.9g,\"start\":%.9g,"
                     "\"end\":%.9g,\"width\":%.9g,\"state\":%u}",
                     first ? "" : ",", laser.pos.x, laser.pos.y, laser.angle, laser.startOffset,
                     laser.endOffset, laser.width, laser.state);
        first = false;
    }
    std::fprintf(this->traceFile, "],\"enemies\":[");
    first = true;
    for (size_t slot = 0; slot < sizeof(g_EnemyManager.enemies) / sizeof(g_EnemyManager.enemies[0]); slot++)
    {
        const Enemy &enemy = g_EnemyManager.enemies[slot];
        if (!enemy.flags.active)
        {
            continue;
        }
        std::fprintf(this->traceFile,
                     "%s{\"slot\":%zu,\"x\":%.9g,\"y\":%.9g,\"life\":%d,\"max_life\":%d,"
                     "\"score\":%d,\"boss\":%s,\"ecl_sub\":%u,\"ecl_time\":%d,"
                     "\"ecl_timer_previous\":%d,\"ecl_timer_subframe_bits\":\"0x%08x\","
                     "\"position_bits\":[\"0x%08x\",\"0x%08x\",\"0x%08x\"],"
                     "\"hitbox_bits\":[\"0x%08x\",\"0x%08x\",\"0x%08x\"],"
                     "\"axis_speed_bits\":[\"0x%08x\",\"0x%08x\",\"0x%08x\"],"
                     "\"angle_bits\":\"0x%08x\",\"angular_velocity_bits\":\"0x%08x\","
                     "\"speed_bits\":\"0x%08x\",\"acceleration_bits\":\"0x%08x\","
                     "\"flags\":[%u,%u,%u]}",
                     first ? "" : ",", slot, enemy.position.x, enemy.position.y, enemy.life, enemy.maxLife,
                     enemy.score,
                     enemy.flags.isBoss ? "true" : "false", enemy.currentContext.subId,
                     enemy.currentContext.time.current, enemy.currentContext.time.previous,
                     bit_cast_from_size(enemy.currentContext.time.subFrame), bit_cast_from_size(enemy.position.x),
                     bit_cast_from_size(enemy.position.y), bit_cast_from_size(enemy.position.z),
                     bit_cast_from_size(enemy.hitboxDimensions.x), bit_cast_from_size(enemy.hitboxDimensions.y),
                     bit_cast_from_size(enemy.hitboxDimensions.z), bit_cast_from_size(enemy.axisSpeed.x),
                     bit_cast_from_size(enemy.axisSpeed.y), bit_cast_from_size(enemy.axisSpeed.z),
                     bit_cast_from_size(enemy.angle), bit_cast_from_size(enemy.angularVelocity),
                     bit_cast_from_size(enemy.speed), bit_cast_from_size(enemy.acceleration),
                     reinterpret_cast<const u8 *>(&enemy.flags)[0], reinterpret_cast<const u8 *>(&enemy.flags)[1],
                     reinterpret_cast<const u8 *>(&enemy.flags)[2]);
        first = false;
    }
    std::fprintf(this->traceFile, "]}\n");
    std::fflush(this->traceFile);
    this->playerSpawnTrace = {};
    this->playerBulletUpdateTrace = {};
    this->playerDamageTraceCount = 0;
    this->playerDamageTraceOverflow = false;
}

bool HeadlessRuntime::AdvanceTick()
{
    this->ticks++;
    return this->maxTicks != 0 && this->ticks >= this->maxTicks;
}
