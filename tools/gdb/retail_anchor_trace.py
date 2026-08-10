"""GDB-side frame anchor exporter for the pinned TH06 v1.02h executable.

This script is sourced by a GDB process attached while retail TH06 is in its
Wine startup timing catch-up loop.  It verifies the pinned instruction bytes,
normalizes that Wine-only timing artifact, suppresses physical controller
input, enters replay playback, and records a deliberately small set of raw
gameplay fields at the instruction immediately following
``Chain::RunCalcChain``.

The resulting JSONL is a differential diagnostic, not an equivalence proof.
All addresses are specific to the executable whose SHA-256 is recorded in the
header.  No executable or game-data bytes are written to the trace.
"""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path

import gdb


SCHEMA_VERSION = 1
TARGET_SHA256 = "9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245"
FRAME_BOUNDARY = 0x00420858
SPAWN_BULLETS = 0x00429820
SPAWN_BULLETS_RETURN = 0x0042978B
UPDATE_PLAYER_BULLETS = 0x004291B0
UPDATE_PLAYER_BULLETS_RETURN = 0x0042912C
CALC_DAMAGE_TO_ENEMY = 0x004264B0
CALC_DAMAGE_TO_ENEMY_RETURN = 0x004127D5
MAIN_MENU_UPDATE = 0x0043579F
CONTROLLER_GET_INPUT = 0x0041D820
TIMING_LOOP_START = 0x00420960
TIMING_LOOP_END = 0x00420990
G_LAST_FRAME_TIME = 0x006C6BF8

EXPECTED_FRAME_BYTES = bytes.fromhex("89 45 fc")
EXPECTED_SPAWN_BYTES = bytes.fromhex("55 8b ec")
EXPECTED_SPAWN_RETURN_BYTES = bytes.fromhex("83 c4 08")
EXPECTED_UPDATE_BYTES = bytes.fromhex("55 8b ec")
EXPECTED_UPDATE_RETURN_BYTES = bytes.fromhex("83 c4 04")
EXPECTED_DAMAGE_BYTES = bytes.fromhex("55 8b ec")
EXPECTED_DAMAGE_RETURN_BYTES = bytes.fromhex("89 45 f8")
EXPECTED_MENU_BYTES = bytes.fromhex("55 8b ec")
EXPECTED_CONTROLLER_BYTES = bytes.fromhex("55 8b ec 81 ec 10")
ZERO_CONTROLLER_BYTES = bytes.fromhex("b8 00 00 00 00 c3")

G_SUPERVISOR = 0x006C6D18
G_GAME_MANAGER = 0x0069BCA0
G_RNG = 0x0069D8F8
G_GUI = 0x0069BC30
G_CUR_FRAME_INPUT = 0x0069D904
G_LAST_FRAME_INPUT = 0x0069D908
G_INPUT_HOLD_FRAMES = 0x0069D910
G_PLAYER = 0x006CA628
G_ENEMY_MANAGER = 0x004B79C8
G_ITEM_MANAGER = 0x0069E268
G_MAIN_MENU = 0x006D46C0

SUPERVISOR_CALC_COUNT = G_SUPERVISOR + 0x184
SUPERVISOR_CUR_STATE = G_SUPERVISOR + 0x18C
SUPERVISOR_EFFECTIVE_RATE = G_SUPERVISOR + 0x1A8
SUPERVISOR_FRAMERATE_MULTIPLIER = G_SUPERVISOR + 0x1AC

GM_SCORE = G_GAME_MANAGER + 0x004
GM_DIFFICULTY = G_GAME_MANAGER + 0x010
GM_IS_IN_REPLAY = G_GAME_MANAGER + 0x01C
GM_DEATHS = G_GAME_MANAGER + 0x020
GM_BOMBS_USED = G_GAME_MANAGER + 0x024
GM_IS_TIME_STOPPED = G_GAME_MANAGER + 0x02C
GM_CURRENT_POWER = G_GAME_MANAGER + 0x1810
GM_NUM_RETRIES = G_GAME_MANAGER + 0x1818
GM_LIVES = G_GAME_MANAGER + 0x181A
GM_BOMBS = G_GAME_MANAGER + 0x181B
GM_CHARACTER = G_GAME_MANAGER + 0x181D
GM_SHOT_TYPE = G_GAME_MANAGER + 0x181E
GM_DEMO_MODE = G_GAME_MANAGER + 0x1824
GM_GAME_FRAMES = G_GAME_MANAGER + 0x1A30
GM_CURRENT_STAGE = G_GAME_MANAGER + 0x1A34
GM_MOVEMENT_MIN_X = G_GAME_MANAGER + 0x1A4C
GM_MOVEMENT_MIN_Y = G_GAME_MANAGER + 0x1A50
GM_MOVEMENT_SIZE_X = G_GAME_MANAGER + 0x1A54
GM_MOVEMENT_SIZE_Y = G_GAME_MANAGER + 0x1A58
GM_RANK = G_GAME_MANAGER + 0x1A70
GM_SUBRANK = G_GAME_MANAGER + 0x1A7C

RNG_SEED = G_RNG
RNG_GENERATION = G_RNG + 0x004

PLAYER_X = G_PLAYER + 0x440
PLAYER_Y = G_PLAYER + 0x444
PLAYER_Z = G_PLAYER + 0x448
PLAYER_HORIZONTAL_MULTIPLIER = G_PLAYER + 0x9D0
PLAYER_VERTICAL_MULTIPLIER = G_PLAYER + 0x9D4
PLAYER_RESPAWN_TIMER = G_PLAYER + 0x9D8
PLAYER_STATE = G_PLAYER + 0x9E0
PLAYER_IS_FOCUS = G_PLAYER + 0x9E3
PLAYER_ORTHOGONAL_SPEED = G_PLAYER + 0x9F4
PLAYER_ORTHOGONAL_FOCUS_SPEED = G_PLAYER + 0x9F8
PLAYER_DIAGONAL_SPEED = G_PLAYER + 0x9FC
PLAYER_DIAGONAL_FOCUS_SPEED = G_PLAYER + 0xA00
PLAYER_PREVIOUS_FRAME_INPUT = G_PLAYER + 0xA18
PLAYER_FIRE_BULLET_TIMER_PREVIOUS = G_PLAYER + 0x75A8
PLAYER_FIRE_BULLET_TIMER_SUBFRAME = G_PLAYER + 0x75AC
PLAYER_FIRE_BULLET_TIMER_CURRENT = G_PLAYER + 0x75B0
PLAYER_INVULNERABILITY_TIMER_PREVIOUS = G_PLAYER + 0x75B4
PLAYER_INVULNERABILITY_TIMER_SUBFRAME = G_PLAYER + 0x75B8
PLAYER_INVULNERABILITY_TIMER_CURRENT = G_PLAYER + 0x75BC
PLAYER_BOMB_IS_IN_USE = G_PLAYER + 0x75C8
PLAYER_LAST_ENEMY_HIT = G_PLAYER + 0xA1C

PLAYER_ORB_0 = G_PLAYER + 0x4A0
PLAYER_ORB_1 = G_PLAYER + 0x4AC
PLAYER_BULLETS = G_PLAYER + 0xA28
PLAYER_BULLET_COUNT = 80
PLAYER_BULLET_SIZE = 0x158

ANM_TIMER = 0x030
ANM_FLAGS = 0x080
ANM_POS = 0x090
ANM_ACTIVE_SPRITE = 0x0B0
ANM_FILE_INDEX = 0x0B4
ANM_SPRITE = 0x0C0
ANM_LOADED_SPRITE_HEIGHT = 0x02C
ANM_LOADED_SPRITE_WIDTH = 0x030
PLAYER_BULLET_POSITION = 0x110
PLAYER_BULLET_SIZE_VECTOR = 0x11C
PLAYER_BULLET_VELOCITY = 0x128
PLAYER_BULLET_SIDEWAYS_MOTION = 0x130
PLAYER_BULLET_UNK_134 = 0x134
PLAYER_BULLET_TIMER = 0x140
PLAYER_BULLET_DAMAGE = 0x14C
PLAYER_BULLET_STATE = 0x14E
PLAYER_BULLET_TYPE = 0x150
PLAYER_BULLET_UNK_152 = 0x152
PLAYER_BULLET_SPAWN_POSITION = 0x154

ENEMY_ARRAY = G_ENEMY_MANAGER + 0xED0
ENEMY_COUNT = 256
ENEMY_SIZE = 0xEC8
ENEMY_CONTEXT = 0x990
ENEMY_CONTEXT_TIMER = ENEMY_CONTEXT + 4
ENEMY_CONTEXT_SUB_ID = ENEMY_CONTEXT + 0x48
ENEMY_POSITION = 0xC6C
ENEMY_HITBOX = 0xC78
ENEMY_AXIS_SPEED = 0xC84
ENEMY_ANGLE = 0xC90
ENEMY_ANGULAR_VELOCITY = 0xC94
ENEMY_SPEED = 0xC98
ENEMY_ACCELERATION = 0xC9C
ENEMY_LIFE = 0xCE4
ENEMY_MAX_LIFE = 0xCE8
ENEMY_SCORE = 0xCEC
ENEMY_FLAGS = 0xE50
ENEMY_MANAGER_RANDOM_ITEM_SPAWN_INDEX = G_ENEMY_MANAGER + 0xEE5B8
ENEMY_MANAGER_RANDOM_ITEM_TABLE_INDEX = G_ENEMY_MANAGER + 0xEE5BA

ITEM_COUNT = 512
ITEM_SIZE = 0x144
ITEM_CURRENT_POSITION = 0x110
ITEM_START_POSITION = 0x11C
ITEM_TARGET_POSITION = 0x128
ITEM_TIMER = 0x134
ITEM_TYPE = 0x140
ITEM_IS_IN_USE = 0x141
ITEM_UNK_142 = 0x142
ITEM_STATE = 0x143
ITEM_MANAGER_NEXT_INDEX = G_ITEM_MANAGER + 0x28944
ITEM_MANAGER_ITEM_COUNT = G_ITEM_MANAGER + 0x28948

MENU_GAME_STATE = G_MAIN_MENU + 0x81F0
MENU_STATE_TIMER = G_MAIN_MENU + 0x81F4
MENU_IDLE_FRAMES = G_MAIN_MENU + 0x81F8
STATE_MAIN_MENU = 1
STATE_REPLAY_LOAD = 12
STATE_REPLAY_LOAD_SELECT = 13
STATE_REPLAY_SELECT = 15
TH_BUTTON_SHOOT = 1


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return default if raw is None else int(raw, 0)


OUTPUT = Path(os.environ["ZKTH06_RETAIL_TRACE_OUTPUT"])
FRAME_LIMIT = _env_int("ZKTH06_RETAIL_TRACE_FRAMES", 100)
WINE_VERSION = os.environ.get("ZKTH06_WINE_VERSION", "unknown")
GDB_VERSION = os.environ.get("ZKTH06_GDB_VERSION", "unknown")
REPLAY_SHA256 = os.environ.get("ZKTH06_RETAIL_REPLAY_SHA256", "unknown")
CONFIG_SHA256 = os.environ.get("ZKTH06_RETAIL_CONFIG_SHA256", "unknown")

if FRAME_LIMIT <= 0:
    raise RuntimeError("ZKTH06_RETAIL_TRACE_FRAMES must be positive")


class Memory:
    def __init__(self) -> None:
        self.inferior = gdb.selected_inferior()

    def read(self, address: int, size: int) -> bytes:
        return bytes(self.inferior.read_memory(address, size))

    def write(self, address: int, value: bytes) -> None:
        self.inferior.write_memory(address, value)

    def u8(self, address: int) -> int:
        return self.read(address, 1)[0]

    def i8(self, address: int) -> int:
        return int.from_bytes(self.read(address, 1), "little", signed=True)

    def u16(self, address: int) -> int:
        return int.from_bytes(self.read(address, 2), "little")

    def i16(self, address: int) -> int:
        return int.from_bytes(self.read(address, 2), "little", signed=True)

    def u32(self, address: int) -> int:
        return int.from_bytes(self.read(address, 4), "little")

    def i32(self, address: int) -> int:
        return int.from_bytes(self.read(address, 4), "little", signed=True)

    def put_u16(self, address: int, value: int) -> None:
        self.inferior.write_memory(address, int(value).to_bytes(2, "little"))

    def put_u32(self, address: int, value: int) -> None:
        self.inferior.write_memory(address, int(value).to_bytes(4, "little"))


memory = Memory()


def require_bytes(address: int, expected: bytes, role: str) -> None:
    actual = memory.read(address, len(expected))
    if actual != expected:
        raise RuntimeError(
            f"{role} bytes do not match pinned v1.02h executable at 0x{address:08x}: "
            f"expected={expected.hex()} actual={actual.hex()}"
        )


pc = int(gdb.parse_and_eval("$pc"))
if not TIMING_LOOP_START <= pc <= TIMING_LOOP_END:
    timing_breakpoint = gdb.Breakpoint("*0x0042097e", internal=False)
    gdb.execute("continue", to_string=True)
    timing_breakpoint.delete()
    pc = int(gdb.parse_and_eval("$pc"))
    if pc != 0x0042097E:
        raise RuntimeError(
            f"retail process did not reach the expected Wine timing loop: pc=0x{pc:08x}"
        )
if memory.i32(MENU_GAME_STATE) != STATE_MAIN_MENU:
    raise RuntimeError("retail process did not reach the initialized main menu")
require_bytes(FRAME_BOUNDARY, EXPECTED_FRAME_BYTES, "post-calc anchor")
require_bytes(SPAWN_BULLETS, EXPECTED_SPAWN_BYTES, "Player::SpawnBullets entry")
require_bytes(
    SPAWN_BULLETS_RETURN,
    EXPECTED_SPAWN_RETURN_BYTES,
    "Player::SpawnBullets return site",
)
require_bytes(UPDATE_PLAYER_BULLETS, EXPECTED_UPDATE_BYTES, "Player::UpdatePlayerBullets entry")
require_bytes(
    UPDATE_PLAYER_BULLETS_RETURN,
    EXPECTED_UPDATE_RETURN_BYTES,
    "Player::UpdatePlayerBullets return site",
)
require_bytes(CALC_DAMAGE_TO_ENEMY, EXPECTED_DAMAGE_BYTES, "Player::CalcDamageToEnemy entry")
require_bytes(
    CALC_DAMAGE_TO_ENEMY_RETURN,
    EXPECTED_DAMAGE_RETURN_BYTES,
    "Player::CalcDamageToEnemy EnemyManager return site",
)
require_bytes(MAIN_MENU_UPDATE, EXPECTED_MENU_BYTES, "main-menu update")
require_bytes(CONTROLLER_GET_INPUT, EXPECTED_CONTROLLER_BYTES, "controller input")

# On this Wine host, timeGetTime starts near the host uptime while TH06's
# zero-initialized last-frame value makes the game execute years of catch-up
# iterations.  Copying the already-read current time into the global and
# zeroing the local delta removes only those pre-game iterations.
ebp = int(gdb.parse_and_eval("$ebp"))
memory.write(G_LAST_FRAME_TIME, memory.read(ebp - 0x28, 8))
memory.write(ebp - 0x30, bytes(8))

# XTest events do not reach Wine DirectInput on the validation host.  Returning
# zero is observationally appropriate for replay gameplay because the
# higher-priority replay callback overwrites the complete replay input mask.
memory.write(CONTROLLER_GET_INPUT, ZERO_CONTROLLER_BYTES)
memory.put_u32(MENU_GAME_STATE, STATE_REPLAY_LOAD)
memory.put_u32(MENU_STATE_TIMER, 59)
memory.put_u32(MENU_IDLE_FRAMES, 0)

output = OUTPUT.open("w", encoding="utf-8")


def emit(value: dict[str, object]) -> None:
    output.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    output.flush()


emit(
    {
        "type": "zkth06.retail-anchor-header",
        "schema_version": SCHEMA_VERSION,
        "target_executable_sha256": TARGET_SHA256,
        "replay_sha256": REPLAY_SHA256,
        "config_sha256": CONFIG_SHA256,
        "wine_version": WINE_VERSION,
        "gdb_version": GDB_VERSION,
        "frame_boundary": f"0x{FRAME_BOUNDARY:08x}",
        "frame_boundary_role": "instruction after Chain::RunCalcChain",
        "menu_trigger": f"0x{MAIN_MENU_UPDATE:08x}",
        "controller_patch": "Controller::GetInput returns zero; ReplayManager overwrites input later in calc order",
        "wine_timing_normalization": "pre-game last-frame time set to current time; local catch-up delta set to zero",
        "claim_boundary": "address-bound differential diagnostic; not a proof of decode, reachability, or equivalence",
    }
)


def inject_shoot() -> None:
    memory.put_u16(G_LAST_FRAME_INPUT, 0)
    memory.put_u16(G_CUR_FRAME_INPUT, TH_BUTTON_SHOOT)
    memory.put_u32(G_INPUT_HOLD_FRAMES, 0)


def raw_vec(address: int, count: int) -> list[str]:
    return [f"0x{memory.u32(address + index * 4):08x}" for index in range(count)]


def f32(address: int) -> float:
    return struct.unpack("<f", memory.read(address, 4))[0]


def capture_enemies() -> list[dict[str, object]]:
    enemies: list[dict[str, object]] = []
    for slot in range(ENEMY_COUNT):
        enemy = ENEMY_ARRAY + slot * ENEMY_SIZE
        flags = [memory.u8(enemy + ENEMY_FLAGS + index) for index in range(3)]
        if flags[0] & 0x80 == 0:
            continue
        enemies.append(
            {
                "slot": slot,
                "x": f32(enemy + ENEMY_POSITION),
                "y": f32(enemy + ENEMY_POSITION + 4),
                "life": memory.i32(enemy + ENEMY_LIFE),
                "max_life": memory.i32(enemy + ENEMY_MAX_LIFE),
                "score": memory.i32(enemy + ENEMY_SCORE),
                "boss": bool(flags[1] & 0x08),
                "ecl_sub": memory.u16(enemy + ENEMY_CONTEXT_SUB_ID),
                "ecl_time": memory.i32(enemy + ENEMY_CONTEXT_TIMER + 8),
                "ecl_timer_previous": memory.i32(enemy + ENEMY_CONTEXT_TIMER),
                "ecl_timer_subframe_bits": f"0x{memory.u32(enemy + ENEMY_CONTEXT_TIMER + 4):08x}",
                "position_bits": raw_vec(enemy + ENEMY_POSITION, 3),
                "hitbox_bits": raw_vec(enemy + ENEMY_HITBOX, 3),
                "axis_speed_bits": raw_vec(enemy + ENEMY_AXIS_SPEED, 3),
                "angle_bits": f"0x{memory.u32(enemy + ENEMY_ANGLE):08x}",
                "angular_velocity_bits": f"0x{memory.u32(enemy + ENEMY_ANGULAR_VELOCITY):08x}",
                "speed_bits": f"0x{memory.u32(enemy + ENEMY_SPEED):08x}",
                "acceleration_bits": f"0x{memory.u32(enemy + ENEMY_ACCELERATION):08x}",
                "flags": flags,
            }
        )
    return enemies


def capture_items() -> dict[str, object]:
    active: list[dict[str, object]] = []
    for slot in range(ITEM_COUNT):
        item = G_ITEM_MANAGER + slot * ITEM_SIZE
        if memory.i8(item + ITEM_IS_IN_USE) == 0:
            continue
        active.append(
            {
                "slot": slot,
                "current_position_bits": raw_vec(item + ITEM_CURRENT_POSITION, 3),
                "start_position_bits": raw_vec(item + ITEM_START_POSITION, 3),
                "target_position_bits": raw_vec(item + ITEM_TARGET_POSITION, 3),
                "timer_previous": memory.i32(item + ITEM_TIMER),
                "timer_subframe_bits": f"0x{memory.u32(item + ITEM_TIMER + 4):08x}",
                "timer_current": memory.i32(item + ITEM_TIMER + 8),
                "item_type": memory.i8(item + ITEM_TYPE),
                "is_in_use": memory.i8(item + ITEM_IS_IN_USE),
                "unk_142": memory.i8(item + ITEM_UNK_142),
                "state": memory.i8(item + ITEM_STATE),
            }
        )
    return {
        "next_index": memory.i32(ITEM_MANAGER_NEXT_INDEX),
        "item_count": memory.u32(ITEM_MANAGER_ITEM_COUNT),
        "random_spawn_index": memory.u16(ENEMY_MANAGER_RANDOM_ITEM_SPAWN_INDEX),
        "random_table_index": memory.u16(ENEMY_MANAGER_RANDOM_ITEM_TABLE_INDEX),
        "active_slots": active,
    }


def capture_active_player_bullets() -> tuple[
    list[int], list[dict[str, object]], list[dict[str, object]]
]:
    states: list[int] = []
    active: list[dict[str, object]] = []
    carry: list[dict[str, object]] = []
    for slot in range(PLAYER_BULLET_COUNT):
        bullet = PLAYER_BULLETS + slot * PLAYER_BULLET_SIZE
        state = memory.i16(bullet + PLAYER_BULLET_STATE)
        states.append(state)
        carry.append(
            {
                "sideways_motion_bits": f"0x{memory.u32(bullet + PLAYER_BULLET_SIDEWAYS_MOTION):08x}",
                "unk_134_x_bits": f"0x{memory.u32(bullet + PLAYER_BULLET_UNK_134):08x}",
                "unk_152": memory.i16(bullet + PLAYER_BULLET_UNK_152),
                "spawn_position_idx": memory.i16(
                    bullet + PLAYER_BULLET_SPAWN_POSITION
                ),
            }
        )
        if state == 0:
            continue
        sprite = memory.u32(bullet + ANM_SPRITE)
        if sprite == 0:
            raise RuntimeError(f"active Player bullet slot {slot} has no loaded sprite")
        active.append(
            {
                "slot": slot,
                "state": state,
                "type": memory.i16(bullet + PLAYER_BULLET_TYPE),
                "damage": memory.i16(bullet + PLAYER_BULLET_DAMAGE),
                "spawn_position_idx": memory.i16(
                    bullet + PLAYER_BULLET_SPAWN_POSITION
                ),
                "unk_152": memory.i16(bullet + PLAYER_BULLET_UNK_152),
                "position_bits": raw_vec(bullet + PLAYER_BULLET_POSITION, 3),
                "size_bits": raw_vec(bullet + PLAYER_BULLET_SIZE_VECTOR, 3),
                "velocity_bits": raw_vec(bullet + PLAYER_BULLET_VELOCITY, 2),
                "sideways_motion_bits": f"0x{memory.u32(bullet + PLAYER_BULLET_SIDEWAYS_MOTION):08x}",
                "unk_134_bits": raw_vec(bullet + PLAYER_BULLET_UNK_134, 3),
                "timer_previous": memory.i32(bullet + PLAYER_BULLET_TIMER),
                "timer_subframe_bits": f"0x{memory.u32(bullet + PLAYER_BULLET_TIMER + 4):08x}",
                "timer_current": memory.i32(bullet + PLAYER_BULLET_TIMER + 8),
                "sprite_position_bits": raw_vec(bullet + ANM_POS, 3),
                "sprite_size_bits": [
                    f"0x{memory.u32(sprite + ANM_LOADED_SPRITE_WIDTH):08x}",
                    f"0x{memory.u32(sprite + ANM_LOADED_SPRITE_HEIGHT):08x}",
                ],
                "sprite_timer_previous": memory.i32(bullet + ANM_TIMER),
                "sprite_timer_subframe_bits": f"0x{memory.u32(bullet + ANM_TIMER + 4):08x}",
                "sprite_timer_current": memory.i32(bullet + ANM_TIMER + 8),
                "sprite_flags": memory.u32(bullet + ANM_FLAGS),
                "sprite_active_index": memory.i16(bullet + ANM_ACTIVE_SPRITE),
                "sprite_anm_file_index": memory.i16(bullet + ANM_FILE_INDEX),
            }
        )
    return states, active, carry


def capture_spawn_side() -> dict[str, object]:
    states, active, carry = capture_active_player_bullets()
    return {"slot_states": states, "active_slots": active, "slot_carry": carry}


pending_spawn: dict[str, object] | None = None
pending_bullet_update: dict[str, object] | None = None
pending_damage: dict[str, object] | None = None
frame_damage_calls: list[dict[str, object]] = []


def capture_spawn_entry() -> None:
    global pending_spawn
    if pending_spawn is not None:
        raise RuntimeError("nested or unconsumed Player::SpawnBullets event")
    esp = int(gdb.parse_and_eval("$esp"))
    player = memory.u32(esp + 4)
    timer = memory.u32(esp + 8)
    if player != G_PLAYER or timer >= 30:
        raise RuntimeError(
            f"unexpected Player::SpawnBullets arguments: player=0x{player:08x} timer={timer}"
        )
    pending_spawn = {
        "timer": timer,
        "current_power": memory.u16(GM_CURRENT_POWER),
        "is_focus": memory.u8(PLAYER_IS_FOCUS),
        "player_position_bits": raw_vec(PLAYER_X, 3),
        "orb_position_bits": [raw_vec(PLAYER_ORB_0, 3), raw_vec(PLAYER_ORB_1, 3)],
        "before": capture_spawn_side(),
    }


def capture_spawn_return() -> None:
    if pending_spawn is None or "after" in pending_spawn:
        raise RuntimeError("unpaired Player::SpawnBullets return")
    pending_spawn["after"] = capture_spawn_side()


def capture_bullet_update_entry() -> None:
    global pending_bullet_update
    if pending_bullet_update is not None:
        raise RuntimeError("nested or unconsumed Player::UpdatePlayerBullets event")
    esp = int(gdb.parse_and_eval("$esp"))
    player = memory.u32(esp + 4)
    if player != G_PLAYER:
        raise RuntimeError(
            f"unexpected Player::UpdatePlayerBullets argument: player=0x{player:08x}"
        )
    pending_bullet_update = {
        "last_enemy_hit_bits": raw_vec(PLAYER_LAST_ENEMY_HIT, 3),
        "before": capture_spawn_side(),
    }


def capture_bullet_update_return() -> None:
    if pending_bullet_update is None or "after" in pending_bullet_update:
        raise RuntimeError("unpaired Player::UpdatePlayerBullets return")
    pending_bullet_update["after"] = capture_spawn_side()


def capture_damage_entry() -> None:
    global pending_damage
    if pending_damage is not None:
        raise RuntimeError("nested Player::CalcDamageToEnemy event")
    esp = int(gdb.parse_and_eval("$esp"))
    player = int(gdb.parse_and_eval("$ecx"))
    enemy_position = memory.u32(esp + 4)
    enemy_hitbox = memory.u32(esp + 8)
    hit_with_laser = memory.u32(esp + 12)
    if player != G_PLAYER:
        raise RuntimeError(
            f"unexpected Player::CalcDamageToEnemy this pointer: 0x{player:08x}"
        )
    relative = enemy_position - (ENEMY_ARRAY + ENEMY_POSITION)
    if relative < 0 or relative % ENEMY_SIZE != 0 or relative // ENEMY_SIZE >= ENEMY_COUNT:
        raise RuntimeError(
            f"damage position does not belong to EnemyManager: 0x{enemy_position:08x}"
        )
    if enemy_hitbox != enemy_position + (ENEMY_HITBOX - ENEMY_POSITION):
        raise RuntimeError("damage position/hitbox arguments do not share an Enemy")
    pending_damage = {
        "enemy_position_bits": raw_vec(enemy_position, 3),
        "enemy_hitbox_bits": raw_vec(enemy_hitbox, 3),
        "bomb_is_in_use": memory.u32(PLAYER_BOMB_IS_IN_USE),
        "before": capture_spawn_side(),
        "_hit_with_laser_address": hit_with_laser,
    }


def capture_damage_return() -> None:
    global pending_damage
    if pending_damage is None:
        raise RuntimeError("unpaired Player::CalcDamageToEnemy return")
    hit_with_laser = int(pending_damage.pop("_hit_with_laser_address"))
    pending_damage.update(
        {
            "damage": int(gdb.parse_and_eval("$eax")) & 0xFFFF_FFFF,
            "hit_with_laser_during_bomb": bool(
                hit_with_laser != 0 and memory.u8(hit_with_laser) != 0
            ),
            "after": capture_spawn_side(),
        }
    )
    if int(pending_damage["damage"]) >= 0x8000_0000:
        pending_damage["damage"] = int(pending_damage["damage"]) - 0x1_0000_0000
    frame_damage_calls.append(pending_damage)
    pending_damage = None


def capture_frame(index: int) -> None:
    global pending_spawn, pending_bullet_update, pending_damage, frame_damage_calls
    game_frame = memory.u32(GM_GAME_FRAMES)
    emit(
        {
            "type": "zkth06.retail-anchor-frame",
            "index": index,
            "calc_count": memory.i32(SUPERVISOR_CALC_COUNT),
            "supervisor_state": memory.i32(SUPERVISOR_CUR_STATE),
            "stage": memory.i32(GM_CURRENT_STAGE),
            "game_frame": game_frame,
            "difficulty": memory.i32(GM_DIFFICULTY),
            "character": memory.u8(GM_CHARACTER),
            "shot_type": memory.u8(GM_SHOT_TYPE),
            "input": memory.u16(G_CUR_FRAME_INPUT),
            "rng_seed": memory.u16(RNG_SEED),
            "rng_generation": memory.u32(RNG_GENERATION),
            "score": memory.u32(GM_SCORE),
            "deaths": memory.i32(GM_DEATHS),
            "bombs_used": memory.i32(GM_BOMBS_USED),
            "is_time_stopped": memory.i8(GM_IS_TIME_STOPPED),
            "gui_has_current_message": int(
                memory.i32(memory.u32(G_GUI + 0x4) + 0x253C) >= 0
            ),
            "num_retries": memory.u8(GM_NUM_RETRIES),
            "current_power": memory.u16(GM_CURRENT_POWER),
            "lives": memory.i8(GM_LIVES),
            "bombs": memory.i8(GM_BOMBS),
            "rank": memory.i32(GM_RANK),
            "subrank": memory.i32(GM_SUBRANK),
            "player_x_bits": f"0x{memory.u32(PLAYER_X):08x}",
            "player_y_bits": f"0x{memory.u32(PLAYER_Y):08x}",
            "player_z_bits": f"0x{memory.u32(PLAYER_Z):08x}",
            "player_state": memory.i8(PLAYER_STATE),
            "player_respawn_timer": memory.i32(PLAYER_RESPAWN_TIMER),
            "player_bomb_is_in_use": memory.u32(PLAYER_BOMB_IS_IN_USE),
            "player_invulnerability_timer_previous": memory.i32(PLAYER_INVULNERABILITY_TIMER_PREVIOUS),
            "player_invulnerability_timer_subframe_bits": f"0x{memory.u32(PLAYER_INVULNERABILITY_TIMER_SUBFRAME):08x}",
            "player_invulnerability_timer_current": memory.i32(PLAYER_INVULNERABILITY_TIMER_CURRENT),
            "player_is_focus": memory.u8(PLAYER_IS_FOCUS),
            "player_previous_frame_input": memory.u16(PLAYER_PREVIOUS_FRAME_INPUT),
            "player_fire_bullet_timer_previous": memory.i32(PLAYER_FIRE_BULLET_TIMER_PREVIOUS),
            "player_fire_bullet_timer_subframe_bits": f"0x{memory.u32(PLAYER_FIRE_BULLET_TIMER_SUBFRAME):08x}",
            "player_fire_bullet_timer_current": memory.i32(PLAYER_FIRE_BULLET_TIMER_CURRENT),
            "movement_min_x_bits": f"0x{memory.u32(GM_MOVEMENT_MIN_X):08x}",
            "movement_min_y_bits": f"0x{memory.u32(GM_MOVEMENT_MIN_Y):08x}",
            "movement_size_x_bits": f"0x{memory.u32(GM_MOVEMENT_SIZE_X):08x}",
            "movement_size_y_bits": f"0x{memory.u32(GM_MOVEMENT_SIZE_Y):08x}",
            "horizontal_multiplier_bits": f"0x{memory.u32(PLAYER_HORIZONTAL_MULTIPLIER):08x}",
            "vertical_multiplier_bits": f"0x{memory.u32(PLAYER_VERTICAL_MULTIPLIER):08x}",
            "orthogonal_speed_bits": f"0x{memory.u32(PLAYER_ORTHOGONAL_SPEED):08x}",
            "orthogonal_focus_speed_bits": f"0x{memory.u32(PLAYER_ORTHOGONAL_FOCUS_SPEED):08x}",
            "diagonal_speed_bits": f"0x{memory.u32(PLAYER_DIAGONAL_SPEED):08x}",
            "diagonal_focus_speed_bits": f"0x{memory.u32(PLAYER_DIAGONAL_FOCUS_SPEED):08x}",
            "effective_rate_bits": f"0x{memory.u32(SUPERVISOR_EFFECTIVE_RATE):08x}",
            "framerate_multiplier_bits": f"0x{memory.u32(SUPERVISOR_FRAMERATE_MULTIPLIER):08x}",
            "x87_control_word": f"0x{int(gdb.parse_and_eval('$fctrl')) & 0xffff:04x}",
            "mxcsr": f"0x{int(gdb.parse_and_eval('$mxcsr')) & 0xffffffff:08x}",
            "player_spawn": pending_spawn,
            "player_bullet_update": pending_bullet_update,
            "player_last_enemy_hit_bits": raw_vec(PLAYER_LAST_ENEMY_HIT, 3),
            "player_bullets_frame": capture_spawn_side(),
            "player_damage_calls": frame_damage_calls,
            "player_damage_trace_overflow": False,
            "items_frame": capture_items(),
            "enemies": capture_enemies(),
        }
    )
    if pending_spawn is not None and "after" not in pending_spawn:
        raise RuntimeError("frame boundary reached before Player::SpawnBullets returned")
    if pending_bullet_update is None or "after" not in pending_bullet_update:
        raise RuntimeError("frame boundary reached without a complete Player::UpdatePlayerBullets event")
    if pending_damage is not None:
        raise RuntimeError("frame boundary reached inside Player::CalcDamageToEnemy")
    pending_spawn = None
    pending_bullet_update = None
    frame_damage_calls = []


# Keep all control flow outside Breakpoint.stop().  Continuing automatically
# from a Python breakpoint callback triggers a GDB 13/Wine WoW64 crash on the
# validation host; an explicit stop/inspect/continue loop is stable and also
# makes every sampled instruction boundary unambiguous.
menu_breakpoint = gdb.Breakpoint(f"*0x{MAIN_MENU_UPDATE:08x}", internal=False)
frame_breakpoint = gdb.Breakpoint(f"*0x{FRAME_BOUNDARY:08x}", internal=False)
spawn_breakpoint = gdb.Breakpoint(f"*0x{SPAWN_BULLETS:08x}", internal=False)
spawn_return_breakpoint = gdb.Breakpoint(
    f"*0x{SPAWN_BULLETS_RETURN:08x}", internal=False
)
update_bullets_breakpoint = gdb.Breakpoint(f"*0x{UPDATE_PLAYER_BULLETS:08x}", internal=False)
update_bullets_return_breakpoint = gdb.Breakpoint(
    f"*0x{UPDATE_PLAYER_BULLETS_RETURN:08x}", internal=False
)
damage_breakpoint = gdb.Breakpoint(f"*0x{CALC_DAMAGE_TO_ENEMY:08x}", internal=False)
damage_return_breakpoint = gdb.Breakpoint(
    f"*0x{CALC_DAMAGE_TO_ENEMY_RETURN:08x}", internal=False
)
replay_selected = False
frame_count = 0

while frame_count < FRAME_LIMIT:
    gdb.execute("continue", to_string=True)
    pc = int(gdb.parse_and_eval("$pc"))
    if pc == MAIN_MENU_UPDATE:
        state = memory.i32(MENU_GAME_STATE)
        timer = memory.i32(MENU_STATE_TIMER)
        if not replay_selected and state == STATE_REPLAY_LOAD_SELECT:
            inject_shoot()
            replay_selected = True
            gdb.write("zkTH06: injected replay-file confirmation\n")
        elif replay_selected and state == STATE_REPLAY_SELECT and timer >= 40:
            inject_shoot()
            menu_breakpoint.delete()
            gdb.write("zkTH06: injected replay-stage confirmation\n")
        continue
    if pc == SPAWN_BULLETS:
        capture_spawn_entry()
        continue
    if pc == SPAWN_BULLETS_RETURN:
        capture_spawn_return()
        continue
    if pc == UPDATE_PLAYER_BULLETS:
        capture_bullet_update_entry()
        continue
    if pc == UPDATE_PLAYER_BULLETS_RETURN:
        capture_bullet_update_return()
        continue
    if pc == CALC_DAMAGE_TO_ENEMY:
        capture_damage_entry()
        continue
    if pc == CALC_DAMAGE_TO_ENEMY_RETURN:
        capture_damage_return()
        continue
    if pc != FRAME_BOUNDARY:
        continue
    if memory.i32(SUPERVISOR_CUR_STATE) != 2:
        continue
    if memory.u32(GM_IS_IN_REPLAY) != 1 or memory.u8(GM_DEMO_MODE) != 0:
        continue
    if memory.u32(GM_GAME_FRAMES) == 0:
        continue
    capture_frame(frame_count)
    frame_count += 1
    if frame_count == 1 or frame_count % 25 == 0 or frame_count == FRAME_LIMIT:
        gdb.write(f"zkTH06: captured retail anchor {frame_count}/{FRAME_LIMIT}\n")

if menu_breakpoint.is_valid():
    menu_breakpoint.delete()
frame_breakpoint.delete()
spawn_breakpoint.delete()
spawn_return_breakpoint.delete()
update_bullets_breakpoint.delete()
update_bullets_return_breakpoint.delete()
damage_breakpoint.delete()
damage_return_breakpoint.delete()
output.close()
gdb.execute("detach")
gdb.execute("quit")
