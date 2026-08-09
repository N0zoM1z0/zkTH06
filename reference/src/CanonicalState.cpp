#include "CanonicalState.hpp"

#include "AnmManager.hpp"
#include "BulletManager.hpp"
#include "Controller.hpp"
#include "EclManager.hpp"
#include "EffectManager.hpp"
#include "EnemyEclInstr.hpp"
#include "EnemyManager.hpp"
#include "GameManager.hpp"
#include "Gui.hpp"
#include "ItemManager.hpp"
#include "Player.hpp"
#include "Rng.hpp"
#include "Stage.hpp"
#include "Supervisor.hpp"

#include <cstdint>
#include <limits>

namespace
{
// This is a deterministic diagnostic projection, not yet a closed gameplay
// state. Keep omissions and overwrite-before-read obligations synchronized
// with docs/state-projection-audit.md.
constexpr u16 SELECTED = CanonicalTrace::SUBSYSTEM_FLAG_SELECTED_FIELDS;
constexpr u16 ABSENT_INDEX = std::numeric_limits<u16>::max();
constexpr u16 INVALID_INDEX = std::numeric_limits<u16>::max() - 1;
constexpr u32 ABSENT_OFFSET = std::numeric_limits<u32>::max();
constexpr u32 INVALID_OFFSET = std::numeric_limits<u32>::max() - 1;

void WriteVec2(CanonicalSink &sink, const ZunVec2 &value)
{
    sink.F32(value.x);
    sink.F32(value.y);
}

void WriteVec3(CanonicalSink &sink, const ZunVec3 &value)
{
    sink.F32(value.x);
    sink.F32(value.y);
    sink.F32(value.z);
}

void WriteVec4(CanonicalSink &sink, const ZunVec4 &value)
{
    sink.F32(value.x);
    sink.F32(value.y);
    sink.F32(value.z);
    sink.F32(value.w);
}

void WriteTimer(CanonicalSink &sink, const ZunTimer &timer)
{
    sink.I32(timer.previous);
    sink.F32(timer.subFrame);
    sink.I32(timer.current);
}

u32 RelativeOffset(const void *pointer, const void *base)
{
    if (pointer == NULL)
    {
        return ABSENT_OFFSET;
    }
    if (base == NULL)
    {
        return INVALID_OFFSET;
    }
    const uintptr_t pointerAddress = reinterpret_cast<uintptr_t>(pointer);
    const uintptr_t baseAddress = reinterpret_cast<uintptr_t>(base);
    if (pointerAddress < baseAddress || pointerAddress - baseAddress >= INVALID_OFFSET)
    {
        return INVALID_OFFSET;
    }
    return static_cast<u32>(pointerAddress - baseAddress);
}

template <typename T, size_t Size> u16 StableIndex(const T *pointer, const T (&array)[Size])
{
    if (pointer == NULL)
    {
        return ABSENT_INDEX;
    }
    const uintptr_t pointerAddress = reinterpret_cast<uintptr_t>(pointer);
    const uintptr_t baseAddress = reinterpret_cast<uintptr_t>(&array[0]);
    const uintptr_t endAddress = baseAddress + sizeof(array);
    if (pointerAddress < baseAddress || pointerAddress >= endAddress || (pointerAddress - baseAddress) % sizeof(T) != 0)
    {
        return INVALID_INDEX;
    }
    return static_cast<u16>((pointerAddress - baseAddress) / sizeof(T));
}

u32 PackAnmFlags(const AnmVmFlags &flags)
{
    return static_cast<u32>(flags.isVisible) | static_cast<u32>(flags.flag1) << 1 |
           static_cast<u32>(flags.blendMode) << 2 | static_cast<u32>(flags.colorOp) << 3 |
           static_cast<u32>(flags.flag4) << 4 | static_cast<u32>(flags.usePosOffset) << 5 |
           static_cast<u32>(flags.flip) << 6 | static_cast<u32>(flags.anchor) << 8 |
           static_cast<u32>(flags.posTime) << 10 | static_cast<u32>(flags.zWriteDisable) << 12 |
           static_cast<u32>(flags.isStopped) << 13;
}

void WriteAnmVm(CanonicalSink &sink, const AnmVm &vm)
{
    WriteVec3(sink, vm.rotation);
    WriteVec3(sink, vm.angleVel);
    sink.F32(vm.scaleY);
    sink.F32(vm.scaleX);
    sink.F32(vm.scaleInterpFinalY);
    sink.F32(vm.scaleInterpFinalX);
    WriteVec2(sink, vm.uvScrollPos);
    WriteTimer(sink, vm.currentTimeInScript);
    sink.U32(vm.color);
    sink.U32(PackAnmFlags(vm.flags));
    sink.I16(vm.alphaInterpEndTime);
    sink.I16(vm.scaleInterpEndTime);
    sink.I16(vm.autoRotate);
    sink.I16(vm.pendingInterrupt);
    sink.I16(vm.posInterpEndTime);
    WriteVec3(sink, vm.pos);
    // Initialize() intentionally leaves disabled interpolation storage alone.
    // Encode it only while ExecuteScript can read it.
    if (vm.scaleInterpEndTime > 0)
    {
        sink.F32(vm.scaleInterpInitialY);
        sink.F32(vm.scaleInterpInitialX);
        WriteTimer(sink, vm.scaleInterpTime);
    }
    sink.I16(vm.activeSpriteIndex);
    sink.I16(vm.anmFileIndex);
    sink.U32(RelativeOffset(vm.currentInstruction, vm.beginingOfScript));
    const u16 spriteIndex = g_AnmManager == NULL ? (vm.sprite == NULL ? ABSENT_INDEX : INVALID_INDEX)
                                                 : StableIndex(vm.sprite, g_AnmManager->sprites);
    sink.U16(spriteIndex);
    if (g_AnmManager != NULL && spriteIndex < sizeof(g_AnmManager->sprites) / sizeof(g_AnmManager->sprites[0]))
    {
        const AnmLoadedSprite &sprite = g_AnmManager->sprites[spriteIndex];
        sink.I32(sprite.sourceFileIndex);
        sink.I32(sprite.spriteId);
        sink.F32(sprite.widthPx);
        sink.F32(sprite.heightPx);
    }
    if (vm.alphaInterpEndTime > 0)
    {
        sink.U32(vm.alphaInterpInitial);
        sink.U32(vm.alphaInterpFinal);
        WriteTimer(sink, vm.alphaInterpTime);
    }
    if (vm.posInterpEndTime != 0)
    {
        WriteVec3(sink, vm.posInterpInitial);
        WriteVec3(sink, vm.posInterpFinal);
        WriteTimer(sink, vm.posInterpTime);
    }
    WriteVec3(sink, vm.posOffset);
}

i16 EclCallbackId(void (*callback)(Enemy *, EclRawInstr *))
{
    if (callback == NULL)
    {
        return -1;
    }
    using Callback = void (*)(Enemy *, EclRawInstr *);
    static constexpr Callback CALLBACKS[] = {
        EnemyEclInstr::ExInsCirnoRainbowBallJank, EnemyEclInstr::ExInsShootAtRandomArea,
        EnemyEclInstr::ExInsShootStarPattern,     EnemyEclInstr::ExInsPatchouliShottypeSetVars,
        EnemyEclInstr::ExInsStage56Func4,         EnemyEclInstr::ExInsStage5Func5,
        EnemyEclInstr::ExInsStage6XFunc6,         EnemyEclInstr::ExInsStage6Func7,
        EnemyEclInstr::ExInsStage6Func8,          EnemyEclInstr::ExInsStage6Func9,
        EnemyEclInstr::ExInsStage6XFunc10,        EnemyEclInstr::ExInsStage6Func11,
        EnemyEclInstr::ExInsStage4Func12,         EnemyEclInstr::ExInsStageXFunc13,
        EnemyEclInstr::ExInsStageXFunc14,         EnemyEclInstr::ExInsStageXFunc15,
        EnemyEclInstr::ExInsStageXFunc16,
    };
    for (size_t index = 0; index < sizeof(CALLBACKS) / sizeof(CALLBACKS[0]); index++)
    {
        if (callback == CALLBACKS[index])
        {
            return static_cast<i16>(index);
        }
    }
    return -2;
}

i16 EffectCallbackId(EffectUpdateCallback callback)
{
    if (callback == NULL)
    {
        return -1;
    }
    static constexpr EffectUpdateCallback CALLBACKS[] = {
        EffectManager::EffectCallbackRandomSplash, EffectManager::EffectCallbackRandomSplashBig,
        EffectManager::EffectCallbackStill,        EffectManager::EffectUpdateCallback4,
        EffectManager::EffectCallbackAttract,      EffectManager::EffectCallbackAttractSlow,
    };
    for (size_t index = 0; index < sizeof(CALLBACKS) / sizeof(CALLBACKS[0]); index++)
    {
        if (callback == CALLBACKS[index])
        {
            return static_cast<i16>(index);
        }
    }
    return -2;
}

void WriteEclContext(CanonicalSink &sink, const EnemyEclContext &context)
{
    sink.U32(RelativeOffset(context.currentInstr, g_EclManager.eclFile));
    WriteTimer(sink, context.time);
    sink.I16(EclCallbackId(context.funcSetFunc));
    sink.I32(context.var0);
    sink.I32(context.var1);
    sink.I32(context.var2);
    sink.I32(context.var3);
    sink.F32(context.float0);
    sink.F32(context.float1);
    sink.F32(context.float2);
    sink.F32(context.float3);
    sink.I32(context.var4);
    sink.I32(context.var5);
    sink.I32(context.var6);
    sink.I32(context.var7);
    sink.I32(context.compareRegister);
    sink.U16(context.subId);
}

void WriteEnemyBulletShooter(CanonicalSink &sink, const EnemyBulletShooter &shooter)
{
    sink.I16(shooter.sprite);
    sink.I16(shooter.spriteOffset);
    WriteVec3(sink, shooter.position);
    sink.F32(shooter.angle1);
    sink.F32(shooter.angle2);
    sink.F32(shooter.speed1);
    sink.F32(shooter.speed2);
    for (f32 value : shooter.exFloats)
    {
        sink.F32(value);
    }
    for (i32 value : shooter.exInts)
    {
        sink.I32(value);
    }
    sink.I32(shooter.unk_40);
    sink.I16(shooter.count1);
    sink.I16(shooter.count2);
    sink.U16(shooter.aimMode);
    sink.U16(shooter.unk_4a);
    sink.U32(shooter.flags);
    sink.I32(static_cast<i32>(shooter.sfx));
}

void WriteEnemyLaserShooter(CanonicalSink &sink, const EnemyLaserShooter &shooter)
{
    sink.I16(shooter.sprite);
    sink.I16(shooter.spriteOffset);
    WriteVec3(sink, shooter.position);
    sink.F32(shooter.angle);
    sink.U32(shooter.unk_14);
    sink.F32(shooter.speed);
    sink.U32(shooter.unk_1c);
    sink.F32(shooter.startOffset);
    sink.F32(shooter.endOffset);
    sink.F32(shooter.startLength);
    sink.F32(shooter.width);
    sink.I32(shooter.startTime);
    sink.I32(shooter.duration);
    sink.I32(shooter.stopTime);
    sink.I32(shooter.grazeDelay);
    sink.I32(shooter.grazeDistance);
    sink.U32(shooter.unk_44);
    sink.U16(shooter.type);
    sink.U32(shooter.flags);
    sink.U32(shooter.unk_50);
}

CanonicalSubsystemDigest CaptureGlobal()
{
    CanonicalSink sink(CanonicalSubsystem::GLOBAL);
    sink.I32(g_Supervisor.calcCount);
    sink.I32(g_Supervisor.wantedState);
    sink.I32(g_Supervisor.curState);
    sink.I32(g_Supervisor.wantedState2);
    sink.I32(g_Supervisor.unk194);
    sink.I32(g_Supervisor.unk198);
    sink.Boolean(g_Supervisor.isInEnding);
    sink.F32(g_Supervisor.effectiveFramerateMultiplier);
    sink.F32(g_Supervisor.framerateMultiplier);
    sink.U8(g_Supervisor.cfg.lifeCount);
    sink.U8(g_Supervisor.cfg.bombCount);
    sink.U8(g_Supervisor.cfg.defaultDifficulty);
    sink.U8(g_Supervisor.cfg.frameskipConfig);
    sink.U32(g_Supervisor.cfg.opts);
    sink.U8(g_Supervisor.defaultConfig.lifeCount);
    sink.U8(g_Supervisor.defaultConfig.bombCount);
    sink.U16(g_LastFrameInput);
    sink.U16(g_CurFrameInput);
    sink.U16(g_IsEigthFrameOfHeldInput);
    sink.U16(g_NumOfFramesInputsWereHeld);

    sink.U32(g_GameManager.guiScore);
    sink.U32(g_GameManager.score);
    sink.U32(g_GameManager.nextScoreIncrement);
    sink.U32(g_GameManager.highScore);
    sink.I32(static_cast<i32>(g_GameManager.difficulty));
    sink.I32(g_GameManager.grazeInStage);
    sink.I32(g_GameManager.grazeInTotal);
    sink.U32(g_GameManager.isInReplay);
    sink.I32(g_GameManager.deaths);
    sink.I32(g_GameManager.bombsUsed);
    sink.I32(g_GameManager.spellcardsCaptured);
    sink.I8(g_GameManager.isTimeStopped);
    sink.U16(g_GameManager.currentPower);
    sink.U16(g_GameManager.pointItemsCollectedInStage);
    sink.U16(g_GameManager.pointItemsCollected);
    sink.U8(g_GameManager.numRetries);
    sink.I8(g_GameManager.powerItemCountForScore);
    sink.I8(g_GameManager.livesRemaining);
    sink.I8(g_GameManager.bombsRemaining);
    sink.I8(g_GameManager.extraLives);
    sink.U8(g_GameManager.character);
    sink.U8(g_GameManager.shotType);
    sink.U8(g_GameManager.isInGameMenu);
    sink.U8(g_GameManager.isInRetryMenu);
    sink.U8(g_GameManager.isInMenu);
    sink.U8(g_GameManager.isGameCompleted);
    sink.U8(g_GameManager.isInPracticeMode);
    sink.U8(g_GameManager.demoMode);
    sink.I32(g_GameManager.demoFrames);
    sink.U16(g_GameManager.randomSeed);
    sink.U32(g_GameManager.gameFrames);
    sink.I32(g_GameManager.currentStage);
    WriteVec2(sink, g_GameManager.arcadeRegionTopLeftPos);
    WriteVec2(sink, g_GameManager.arcadeRegionSize);
    WriteVec2(sink, g_GameManager.playerMovementAreaTopLeftPos);
    WriteVec2(sink, g_GameManager.playerMovementAreaSize);
    sink.F32(g_GameManager.cameraDistance);
    WriteVec3(sink, g_GameManager.stageCameraFacingDir);
    sink.I32(g_GameManager.counat);
    sink.I32(g_GameManager.rank);
    sink.I32(g_GameManager.maxRank);
    sink.I32(g_GameManager.minRank);
    sink.I32(g_GameManager.subRank);
    return sink.Finish(SELECTED, 1);
}

CanonicalSubsystemDigest CaptureRng()
{
    CanonicalSink sink(CanonicalSubsystem::RNG);
    sink.U16(g_Rng.seed);
    sink.U32(g_Rng.generationCount);
    return sink.Finish(SELECTED, 1);
}

CanonicalSubsystemDigest CapturePlayer()
{
    CanonicalSink sink(CanonicalSubsystem::PLAYER);
    WriteAnmVm(sink, g_Player.playerSprite);
    for (const AnmVm &vm : g_Player.orbsSprite)
    {
        WriteAnmVm(sink, vm);
    }
    WriteVec3(sink, g_Player.positionCenter);
    WriteVec3(sink, g_Player.unk_44c);
    WriteVec3(sink, g_Player.hitboxTopLeft);
    WriteVec3(sink, g_Player.hitboxBottomRight);
    WriteVec3(sink, g_Player.grabItemTopLeft);
    WriteVec3(sink, g_Player.grabItemBottomRight);
    WriteVec3(sink, g_Player.hitboxSize);
    WriteVec3(sink, g_Player.grabItemSize);
    for (const ZunVec3 &position : g_Player.orbsPosition)
    {
        WriteVec3(sink, position);
    }
    for (const ZunVec3 &position : g_Player.bombRegionPositions)
    {
        WriteVec3(sink, position);
    }
    for (const ZunVec3 &size : g_Player.bombRegionSizes)
    {
        WriteVec3(sink, size);
    }
    for (i32 damage : g_Player.bombRegionDamages)
    {
        sink.I32(damage);
    }
    for (i32 value : g_Player.unk_838)
    {
        sink.I32(value);
    }
    for (const PlayerRect &projectile : g_Player.bombProjectiles)
    {
        sink.F32(projectile.posX);
        sink.F32(projectile.posY);
        sink.F32(projectile.sizeX);
        sink.F32(projectile.sizeY);
    }
    for (const ZunTimer &timer : g_Player.laserTimer)
    {
        WriteTimer(sink, timer);
    }
    sink.F32(g_Player.horizontalMovementSpeedMultiplierDuringBomb);
    sink.F32(g_Player.verticalMovementSpeedMultiplierDuringBomb);
    sink.I32(g_Player.respawnTimer);
    sink.I32(g_Player.bulletGracePeriod);
    sink.I8(g_Player.playerState);
    sink.U8(g_Player.unk_9e1);
    sink.I8(g_Player.orbState);
    sink.I8(g_Player.isFocus);
    sink.U8(g_Player.unk_9e4);
    WriteTimer(sink, g_Player.focusMovementTimer);
    sink.F32(g_Player.characterData.orthogonalMovementSpeed);
    sink.F32(g_Player.characterData.orthogonalMovementSpeedFocus);
    sink.F32(g_Player.characterData.diagonalMovementSpeed);
    sink.F32(g_Player.characterData.diagonalMovementSpeedFocus);
    sink.I32(static_cast<i32>(g_Player.playerDirection));
    sink.F32(g_Player.previousHorizontalSpeed);
    sink.F32(g_Player.previousVerticalSpeed);
    sink.I16(g_Player.previousFrameInput);
    WriteVec3(sink, g_Player.positionOfLastEnemyHit);
    WriteTimer(sink, g_Player.fireBulletTimer);
    WriteTimer(sink, g_Player.invulnerabilityTimer);
    sink.U32(g_Player.bombInfo.isInUse);
    sink.I32(g_Player.bombInfo.duration);
    WriteTimer(sink, g_Player.bombInfo.timer);
    for (i32 state : g_Player.bombInfo.reimuABombProjectilesState)
    {
        sink.I32(state);
    }
    for (f32 value : g_Player.bombInfo.reimuABombProjectilesRelated)
    {
        sink.F32(value);
    }
    for (const ZunVec3 &position : g_Player.bombInfo.bombRegionPositions)
    {
        WriteVec3(sink, position);
    }
    for (const ZunVec3 &velocity : g_Player.bombInfo.bombRegionVelocities)
    {
        WriteVec3(sink, velocity);
    }
    if (g_Player.bombInfo.isInUse)
    {
        for (const auto &row : g_Player.bombInfo.sprites)
        {
            for (const AnmVm &vm : row)
            {
                WriteAnmVm(sink, vm);
            }
        }
    }
    return sink.Finish(SELECTED, 1);
}

CanonicalSubsystemDigest CapturePlayerBullets()
{
    CanonicalSink sink(CanonicalSubsystem::PLAYER_BULLETS);
    u32 active = 0;
    for (size_t index = 0; index < sizeof(g_Player.bullets) / sizeof(g_Player.bullets[0]); index++)
    {
        const PlayerBullet &bullet = g_Player.bullets[index];
        if (bullet.bulletState == BULLET_STATE_UNUSED)
        {
            continue;
        }
        active++;
        sink.U16(static_cast<u16>(index));
        WriteAnmVm(sink, bullet.sprite);
        WriteVec3(sink, bullet.position);
        WriteVec3(sink, bullet.size);
        WriteVec2(sink, bullet.velocity);
        sink.F32(bullet.sidewaysMotion);
        WriteVec3(sink, bullet.unk_134);
        WriteTimer(sink, bullet.unk_140);
        sink.I16(bullet.damage);
        sink.I16(bullet.bulletState);
        sink.I16(bullet.bulletType);
        sink.I16(bullet.unk_152);
        sink.I16(bullet.spawnPositionIdx);
    }
    return sink.Finish(SELECTED, active);
}

CanonicalSubsystemDigest CaptureEnemies()
{
    CanonicalSink sink(CanonicalSubsystem::ENEMIES_ECL);
    sink.U16(g_EnemyManager.randomItemSpawnIndex);
    sink.U16(g_EnemyManager.randomItemTableIndex);
    sink.I32(g_EnemyManager.enemyCount);
    sink.Boolean(g_EnemyManager.spellcardInfo.isCapturing);
    sink.U32(g_EnemyManager.spellcardInfo.isActive);
    sink.I32(g_EnemyManager.spellcardInfo.captureScore);
    sink.U32(g_EnemyManager.spellcardInfo.idx);
    sink.Boolean(g_EnemyManager.spellcardInfo.usedBomb);
    sink.U32(RelativeOffset(g_EnemyManager.timelineInstr, g_EclManager.eclFile));
    WriteTimer(sink, g_EnemyManager.timelineTime);
    for (const Enemy *boss : g_EnemyManager.bosses)
    {
        sink.U16(StableIndex(boss, g_EnemyManager.enemies));
    }

    u32 active = 0;
    for (size_t index = 0; index < sizeof(g_EnemyManager.enemies) / sizeof(g_EnemyManager.enemies[0]); index++)
    {
        const Enemy &enemy = g_EnemyManager.enemies[index];
        if (!enemy.flags.active)
        {
            continue;
        }
        active++;
        sink.U16(static_cast<u16>(index));
        WriteAnmVm(sink, enemy.primaryVm);
        u8 activeVms = 0;
        for (const AnmVm &vm : enemy.vms)
        {
            activeVms += vm.anmFileIndex >= 0 || vm.currentInstruction != NULL ? 1 : 0;
        }
        sink.U8(activeVms);
        for (size_t vmIndex = 0; vmIndex < sizeof(enemy.vms) / sizeof(enemy.vms[0]); vmIndex++)
        {
            const AnmVm &vm = enemy.vms[vmIndex];
            if (vm.anmFileIndex < 0 && vm.currentInstruction == NULL)
            {
                continue;
            }
            sink.U8(static_cast<u8>(vmIndex));
            WriteAnmVm(sink, vm);
        }
        WriteEclContext(sink, enemy.currentContext);
        sink.I32(enemy.stackDepth);
        const i32 savedContexts = enemy.stackDepth < 0 ? 0 : enemy.stackDepth > 8 ? 8 : enemy.stackDepth;
        sink.U8(static_cast<u8>(savedContexts));
        for (i32 contextIndex = 0; contextIndex < savedContexts; contextIndex++)
        {
            WriteEclContext(sink, enemy.savedContextStack[contextIndex]);
        }
        sink.I32(enemy.unk_c40);
        sink.I32(enemy.deathCallbackSub);
        for (i32 interrupt : enemy.interrupts)
        {
            sink.I32(interrupt);
        }
        sink.I32(enemy.runInterrupt);
        WriteVec3(sink, enemy.position);
        WriteVec3(sink, enemy.hitboxDimensions);
        WriteVec3(sink, enemy.axisSpeed);
        sink.F32(enemy.angle);
        sink.F32(enemy.angularVelocity);
        sink.F32(enemy.speed);
        sink.F32(enemy.acceleration);
        WriteVec3(sink, enemy.shootOffset);
        WriteVec3(sink, enemy.moveInterp);
        WriteVec3(sink, enemy.moveInterpStartPos);
        WriteTimer(sink, enemy.moveInterpTimer);
        sink.I32(enemy.moveInterpStartTime);
        sink.F32(enemy.bulletRankSpeedLow);
        sink.F32(enemy.bulletRankSpeedHigh);
        sink.I16(enemy.bulletRankAmount1Low);
        sink.I16(enemy.bulletRankAmount1High);
        sink.I16(enemy.bulletRankAmount2Low);
        sink.I16(enemy.bulletRankAmount2High);
        sink.I32(enemy.life);
        sink.I32(enemy.maxLife);
        sink.I32(enemy.score);
        WriteTimer(sink, enemy.bossTimer);
        sink.U32(enemy.color);
        WriteEnemyBulletShooter(sink, enemy.bulletProps);
        sink.I32(enemy.shootInterval);
        WriteTimer(sink, enemy.shootIntervalTimer);
        WriteEnemyLaserShooter(sink, enemy.laserProps);
        for (const Laser *laser : enemy.lasers)
        {
            sink.U16(StableIndex(laser, g_BulletManager.lasers));
        }
        sink.I32(enemy.laserStore);
        sink.U8(enemy.deathAnm1);
        sink.U8(enemy.deathAnm2);
        sink.U8(enemy.deathAnm3);
        sink.I8(enemy.itemDrop);
        sink.U8(enemy.bossId);
        sink.U8(enemy.unk_e41);
        WriteTimer(sink, enemy.exInsFunc10Timer);
        sink.U8(enemy.flags.unk1);
        sink.U8(enemy.flags.unk2);
        sink.U8(enemy.flags.unk3);
        sink.U8(enemy.flags.unk4);
        sink.Boolean(enemy.flags.active);
        sink.U8(enemy.flags.unk6);
        sink.U8(enemy.flags.unk7);
        sink.U8(enemy.flags.unk8);
        sink.Boolean(enemy.flags.isBoss);
        sink.U8(enemy.flags.unk10);
        sink.U8(enemy.flags.unk11);
        sink.Boolean(enemy.flags.shouldClampPos);
        sink.U8(enemy.flags.unk13);
        sink.U8(enemy.flags.unk14);
        sink.U8(enemy.flags.unk15);
        sink.U8(enemy.flags.unk16);
        sink.U8(enemy.anmExFlags);
        sink.I16(enemy.anmExDefaults);
        sink.I16(enemy.anmExFarLeft);
        sink.I16(enemy.anmExFarRight);
        sink.I16(enemy.anmExLeft);
        sink.I16(enemy.anmExRight);
        WriteVec2(sink, enemy.lowerMoveLimit);
        WriteVec2(sink, enemy.upperMoveLimit);
        for (const Effect *effect : enemy.effectArray)
        {
            sink.U16(StableIndex(effect, g_EffectManager.effects));
        }
        sink.U32(enemy.effectIdx);
        sink.F32(enemy.effectDistance);
        sink.I32(enemy.lifeCallbackThreshold);
        sink.I32(enemy.lifeCallbackSub);
        sink.I32(enemy.timerCallbackThreshold);
        sink.I32(enemy.timerCallbackSub);
        sink.F32(enemy.exInsFunc6Angle);
        WriteTimer(sink, enemy.exInsFunc6Timer);
    }
    return sink.Finish(SELECTED, active);
}

CanonicalSubsystemDigest CaptureEnemyBullets()
{
    CanonicalSink sink(CanonicalSubsystem::ENEMY_BULLETS);
    sink.I32(g_BulletManager.nextBulletIndex);
    sink.I32(g_BulletManager.bulletCount);
    WriteTimer(sink, g_BulletManager.time);
    u32 active = 0;
    for (size_t index = 0; index < sizeof(g_BulletManager.bullets) / sizeof(g_BulletManager.bullets[0]); index++)
    {
        const Bullet &bullet = g_BulletManager.bullets[index];
        if (bullet.state == 0)
        {
            continue;
        }
        active++;
        sink.U16(static_cast<u16>(index));
        WriteVec3(sink, bullet.pos);
        WriteVec3(sink, bullet.velocity);
        WriteVec3(sink, bullet.ex4Acceleration);
        sink.F32(bullet.speed);
        sink.F32(bullet.ex5Float0);
        sink.F32(bullet.dirChangeSpeed);
        sink.F32(bullet.angle);
        sink.F32(bullet.ex5Float1);
        sink.F32(bullet.dirChangeRotation);
        WriteTimer(sink, bullet.timer);
        sink.I32(bullet.ex5Int0);
        sink.I32(bullet.dirChangeInterval);
        sink.I32(bullet.dirChangeNumTimes);
        sink.I32(bullet.dirChangeMaxTimes);
        sink.U16(bullet.exFlags);
        sink.I16(bullet.spriteOffset);
        sink.U16(bullet.unk_5bc);
        sink.U16(bullet.state);
        sink.U16(bullet.unk_5c0);
        sink.U8(bullet.unk_5c2);
        sink.U8(bullet.isGrazed);
        WriteVec3(sink, bullet.sprites.grazeSize);
        sink.U8(bullet.sprites.unk_55c);
        sink.U8(bullet.sprites.bulletHeight);
        WriteAnmVm(sink, bullet.sprites.spriteBullet);
        sink.I16(bullet.sprites.spriteBullet.baseSpriteIndex);
        sink.U8(static_cast<u8>(bullet.state >= 2 && bullet.state <= 5 ? bullet.state : 0));
        if (bullet.state == 2)
        {
            WriteAnmVm(sink, bullet.sprites.spriteSpawnEffectFast);
        }
        else if (bullet.state == 3)
        {
            WriteAnmVm(sink, bullet.sprites.spriteSpawnEffectNormal);
        }
        else if (bullet.state == 4)
        {
            WriteAnmVm(sink, bullet.sprites.spriteSpawnEffectSlow);
        }
        else if (bullet.state == 5)
        {
            WriteAnmVm(sink, bullet.sprites.spriteSpawnEffectDonut);
        }
    }
    return sink.Finish(SELECTED, active);
}

CanonicalSubsystemDigest CaptureLasers()
{
    CanonicalSink sink(CanonicalSubsystem::LASERS);
    u32 active = 0;
    for (size_t index = 0; index < sizeof(g_BulletManager.lasers) / sizeof(g_BulletManager.lasers[0]); index++)
    {
        const Laser &laser = g_BulletManager.lasers[index];
        if (!laser.inUse)
        {
            continue;
        }
        active++;
        sink.U16(static_cast<u16>(index));
        WriteAnmVm(sink, laser.vm0);
        WriteAnmVm(sink, laser.vm1);
        WriteVec3(sink, laser.pos);
        sink.F32(laser.angle);
        sink.F32(laser.startOffset);
        sink.F32(laser.endOffset);
        sink.F32(laser.startLength);
        sink.F32(laser.width);
        sink.F32(laser.speed);
        sink.I32(laser.startTime);
        sink.I32(laser.grazeDelay);
        sink.I32(laser.duration);
        sink.I32(laser.endTime);
        sink.I32(laser.grazeInterval);
        sink.I32(laser.inUse);
        WriteTimer(sink, laser.timer);
        sink.U16(laser.flags);
        sink.I16(laser.color);
        sink.U8(laser.state);
    }
    return sink.Finish(SELECTED, active);
}

CanonicalSubsystemDigest CaptureItems()
{
    CanonicalSink sink(CanonicalSubsystem::ITEMS);
    sink.I32(g_ItemManager.nextIndex);
    sink.U32(g_ItemManager.itemCount);
    u32 active = 0;
    for (size_t index = 0; index < sizeof(g_ItemManager.items) / sizeof(g_ItemManager.items[0]); index++)
    {
        const Item &item = g_ItemManager.items[index];
        if (!item.isInUse)
        {
            continue;
        }
        active++;
        sink.U16(static_cast<u16>(index));
        WriteAnmVm(sink, item.sprite);
        WriteVec3(sink, item.currentPosition);
        WriteVec3(sink, item.startPosition);
        WriteVec3(sink, item.targetPosition);
        WriteTimer(sink, item.timer);
        sink.I8(item.itemType);
        sink.I8(item.isInUse);
        sink.I8(item.unk_142);
        sink.I8(item.state);
    }
    return sink.Finish(SELECTED, active);
}

void WriteStageCamera(CanonicalSink &sink, const StageCameraSky &camera)
{
    sink.F32(camera.nearPlane);
    sink.F32(camera.farPlane);
    sink.U32(camera.color);
}

CanonicalSubsystemDigest CaptureStage()
{
    CanonicalSink sink(CanonicalSubsystem::STAGE);
    sink.I32(g_Stage.quadCount);
    sink.I32(g_Stage.objectsCount);
    WriteTimer(sink, g_Stage.scriptTime);
    sink.I32(g_Stage.instructionIndex);
    WriteTimer(sink, g_Stage.timer);
    sink.U32(g_Stage.stage);
    WriteVec3(sink, g_Stage.position);
    WriteStageCamera(sink, g_Stage.skyFog);
    WriteStageCamera(sink, g_Stage.skyFogInterpInitial);
    WriteStageCamera(sink, g_Stage.skyFogInterpFinal);
    sink.I32(g_Stage.skyFogInterpDuration);
    WriteTimer(sink, g_Stage.skyFogInterpTimer);
    sink.I8(g_Stage.skyFogNeedsSetup);
    sink.I32(static_cast<i32>(g_Stage.spellcardState));
    sink.I32(g_Stage.ticksSinceSpellcardStarted);
    sink.U8(g_Stage.unpauseFlag);
    WriteVec3(sink, g_Stage.facingDirInterpInitial);
    WriteVec3(sink, g_Stage.facingDirInterpFinal);
    sink.I32(g_Stage.facingDirInterpDuration);
    WriteTimer(sink, g_Stage.facingDirInterpTimer);
    WriteVec3(sink, g_Stage.positionInterpFinal);
    sink.I32(g_Stage.positionInterpEndTime);
    WriteVec3(sink, g_Stage.positionInterpInitial);
    sink.I32(g_Stage.positionInterpStartTime);
    sink.Boolean(g_Stage.quadVms != NULL);
    if (g_Stage.quadVms != NULL)
    {
        for (i32 index = 0; index < g_Stage.quadCount; index++)
        {
            WriteAnmVm(sink, g_Stage.quadVms[index]);
        }
    }
    sink.Boolean(g_Stage.objects != NULL);
    if (g_Stage.objects != NULL)
    {
        for (i32 index = 0; index < g_Stage.objectsCount; index++)
        {
            const RawStageObject *object = g_Stage.objects[index];
            sink.Boolean(object != NULL);
            if (object != NULL)
            {
                sink.I16(object->id);
                sink.I8(object->zLevel);
                sink.I8(object->flags);
            }
        }
    }
    if (g_Stage.spellcardState >= RUNNING)
    {
        WriteAnmVm(sink, g_Stage.spellcardBackground);
    }
    return sink.Finish(SELECTED, 1);
}

void WriteFormattedText(CanonicalSink &sink, const GuiFormattedText &text)
{
    WriteVec3(sink, text.pos);
    sink.I32(text.fmtArg);
    sink.I32(text.isShown);
    WriteTimer(sink, text.timer);
}

CanonicalSubsystemDigest CaptureGui()
{
    CanonicalSink sink(CanonicalSubsystem::GUI_MESSAGE);
    sink.U8(g_Gui.flags.flag0);
    sink.U8(g_Gui.flags.flag1);
    sink.U8(g_Gui.flags.flag2);
    sink.U8(g_Gui.flags.flag3);
    sink.U8(g_Gui.flags.flag4);
    sink.F32(g_Gui.bombSpellcardBarLength);
    sink.F32(g_Gui.blueSpellcardBarLength);
    sink.U32(g_Gui.bossUIOpacity);
    sink.I32(g_Gui.eclSetLives);
    sink.I32(g_Gui.spellcardSecondsRemaining);
    sink.I32(g_Gui.lastSpellcardSecondsRemaining);
    sink.Boolean(g_Gui.bossPresent);
    sink.F32(g_Gui.bossHealthBar1);
    sink.F32(g_Gui.bossHealthBar2);
    sink.Boolean(g_Gui.impl != NULL);
    if (g_Gui.impl == NULL)
    {
        return sink.Finish(SELECTED, 0);
    }
    sink.U8(g_Gui.impl->bossHealthBarState);
    sink.U32(g_Gui.impl->finishedStage);
    sink.U32(g_Gui.impl->stageScore);
    WriteFormattedText(sink, g_Gui.impl->bonusScore);
    WriteFormattedText(sink, g_Gui.impl->fullPowerMode);
    WriteFormattedText(sink, g_Gui.impl->spellCardBonus);
    const GuiMsgVm &message = g_Gui.impl->msg;
    sink.I32(message.currentMsgIdx);
    sink.U32(RelativeOffset(message.currentInstr, message.msgFile));
    WriteTimer(sink, message.timer);
    sink.I32(message.framesElapsedDuringPause);
    sink.U32(message.fontSize);
    sink.U32(message.ignoreWaitCounter);
    sink.U8(message.dialogueSkippable);
    for (const AnmVm &vm : g_Gui.impl->vms)
    {
        WriteAnmVm(sink, vm);
    }
    WriteAnmVm(sink, g_Gui.impl->stageNameSprite);
    WriteAnmVm(sink, g_Gui.impl->songNameSprite);
    WriteAnmVm(sink, g_Gui.impl->playerSpellcardPortrait);
    WriteAnmVm(sink, g_Gui.impl->enemySpellcardPortrait);
    WriteAnmVm(sink, g_Gui.impl->bombSpellcardName);
    WriteAnmVm(sink, g_Gui.impl->enemySpellcardName);
    WriteAnmVm(sink, g_Gui.impl->bombSpellcardBackground);
    WriteAnmVm(sink, g_Gui.impl->enemySpellcardBackground);
    WriteAnmVm(sink, g_Gui.impl->loadingScreenSprite);
    for (const AnmVm &vm : message.portraits)
    {
        WriteAnmVm(sink, vm);
    }
    for (const AnmVm &vm : message.dialogueLines)
    {
        WriteAnmVm(sink, vm);
    }
    for (const AnmVm &vm : message.introLines)
    {
        WriteAnmVm(sink, vm);
    }
    return sink.Finish(SELECTED, 1);
}

CanonicalSubsystemDigest CaptureEffects()
{
    CanonicalSink sink(CanonicalSubsystem::EFFECTS);
    sink.I32(g_EffectManager.nextIndex);
    sink.I32(g_EffectManager.activeEffects);
    u32 active = 0;
    for (size_t index = 0; index < sizeof(g_EffectManager.effects) / sizeof(g_EffectManager.effects[0]); index++)
    {
        const Effect &effect = g_EffectManager.effects[index];
        // Inactive effect residue is a known open closure obligation. Some
        // fields survive allocation and can become future-live on reuse.
        if (!effect.inUseFlag)
        {
            continue;
        }
        active++;
        sink.U16(static_cast<u16>(index));
        WriteAnmVm(sink, effect.vm);
        WriteVec3(sink, effect.pos1);
        WriteVec3(sink, effect.unk_11c);
        WriteVec3(sink, effect.unk_128);
        WriteVec3(sink, effect.position);
        WriteVec3(sink, effect.pos2);
        WriteVec4(sink, effect.quaternion);
        sink.F32(effect.unk_15c);
        sink.F32(effect.angleRelated);
        WriteTimer(sink, effect.timer);
        sink.I32(effect.unk_170);
        sink.I16(EffectCallbackId(effect.updateCallback));
        sink.I8(effect.inUseFlag);
        sink.I8(effect.effectId);
        sink.I8(effect.unk_17a);
        sink.I8(effect.unk_17b);
    }
    return sink.Finish(SELECTED, active);
}
} // namespace

CanonicalSubsystemDigests CanonicalState::Capture()
{
    return {
        CaptureGlobal(),       CaptureRng(),          CapturePlayer(), CapturePlayerBullets(),
        CaptureEnemies(),      CaptureEnemyBullets(), CaptureLasers(), CaptureItems(),
        CaptureStage(),        CaptureGui(),          CaptureEffects(),
    };
}
