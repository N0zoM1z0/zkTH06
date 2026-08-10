#![no_std]
#![forbid(unsafe_code)]

//! Local refinement of the pinned `Player::SpawnBullets` callback for Reimu A.
//!
//! The transition starts with the complete 80-entry bullet-state array and the
//! four fields that the non-laser callback deliberately leaves untouched. It
//! selects one of the first three Reimu-A power ranks, scans slots in retail
//! order, and returns the initialized geometry.  ANM execution, bullet motion,
//! collision, and linkage between separate calls remain outside this local
//! transition.

use zkth06_player_motion::pc24::{self, ArithmeticError};

pub const PLAYER_BULLET_SLOTS: usize = 80;
pub const MAX_REIMU_A_RANK3_BULLETS: usize = 4;
pub const BULLET_STATE_UNUSED: u8 = 0;
pub const BULLET_STATE_FIRED: u8 = 1;
pub const BULLET_STATE_COLLIDED: u8 = 2;
pub const BULLET_TYPE_0: u8 = 0;
pub const BULLET_TYPE_1: u8 = 1;
pub const PLAYER_BULLET_ANM: u16 = 0x440;
pub const REIMU_A_ORB_BULLET_ANM: u16 = 0x441;
pub const BULLET_Z_BITS: u32 = 0x3efd_70a4;
pub const ONE_BITS: u32 = 0x3f80_0000;
pub const ZERO_BITS: u32 = 0;
pub const POPUP_TIMER_PREVIOUS: i32 = -999;

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Vec2Bits {
    pub x: u32,
    pub y: u32,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Vec3Bits {
    pub x: u32,
    pub y: u32,
    pub z: u32,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct SlotCarry {
    pub sideways_motion_bits: u32,
    pub unk_134_x_bits: u32,
    pub unk_152: i16,
    pub stored_spawn_position_idx: i16,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SpawnInput {
    pub timer: u8,
    pub current_power: u16,
    pub player_position: Vec3Bits,
    pub orb_positions: [Vec3Bits; 2],
    pub slot_states: [u8; PLAYER_BULLET_SLOTS],
    pub slot_carry: [SlotCarry; PLAYER_BULLET_SLOTS],
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct InitializedBullet {
    pub slot: u8,
    pub bullet_data_index: u8,
    pub position: Vec3Bits,
    pub size: Vec3Bits,
    pub velocity: Vec2Bits,
    pub sideways_motion_bits: u32,
    pub unk_134: Vec3Bits,
    pub timer_previous: i32,
    pub timer_subframe_bits: u32,
    pub timer_current: i32,
    pub damage: i16,
    pub bullet_type: u8,
    pub unk_152: i16,
    pub stored_spawn_position_idx: i16,
    pub source_spawn_position_idx: u8,
    pub requested_anm_script: u16,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SpawnOutput {
    pub slot_states: [u8; PLAYER_BULLET_SLOTS],
    pub allocations: [InitializedBullet; MAX_REIMU_A_RANK3_BULLETS],
    pub allocation_count: u8,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SpawnError {
    TimerOutOfRange(u8),
    UnsupportedPower(u16),
    InvalidSlotState { slot: u8, state: u8 },
    InvalidSourcePosition(u8),
    Arithmetic(ArithmeticError),
}

impl From<ArithmeticError> for SpawnError {
    fn from(value: ArithmeticError) -> Self {
        Self::Arithmetic(value)
    }
}

#[derive(Clone, Copy)]
struct BulletData {
    wait: u8,
    frame: u8,
    motion: Vec2Bits,
    size: Vec2Bits,
    direction_bits: u32,
    speed_bits: u32,
    velocity: Vec2Bits,
    damage: i16,
    source_spawn_position_idx: u8,
    bullet_type: u8,
    anm_script: u16,
}

const STRAIGHT: BulletData = BulletData {
    wait: 5,
    frame: 0,
    motion: Vec2Bits { x: 0, y: 0 },
    size: Vec2Bits {
        x: 0x4140_0000,
        y: 0x4140_0000,
    },
    direction_bits: 0xbfc9_0fdb,
    speed_bits: 0x4140_0000,
    velocity: Vec2Bits {
        x: 0xb50c_cde2,
        y: 0xc140_0000,
    },
    damage: 48,
    source_spawn_position_idx: 0,
    bullet_type: BULLET_TYPE_0,
    anm_script: PLAYER_BULLET_ANM,
};

const HOMING_LEFT: BulletData = BulletData {
    wait: 30,
    frame: 0,
    motion: Vec2Bits { x: 0, y: 0 },
    size: Vec2Bits {
        x: 0x4140_0000,
        y: 0x4140_0000,
    },
    direction_bits: 0xc006_0a92,
    speed_bits: 0x4120_0000,
    velocity: Vec2Bits {
        x: 0xc0a0_0001,
        y: 0xc10a_9066,
    },
    damage: 14,
    source_spawn_position_idx: 1,
    bullet_type: BULLET_TYPE_1,
    anm_script: REIMU_A_ORB_BULLET_ANM,
};

const HOMING_RIGHT: BulletData = BulletData {
    direction_bits: 0xbf86_0a92,
    velocity: Vec2Bits {
        x: 0x409f_ffff,
        y: 0xc10a_9067,
    },
    source_spawn_position_idx: 2,
    ..HOMING_LEFT
};

const SPREAD_LEFT: BulletData = BulletData {
    motion: Vec2Bits {
        x: 0xc080_0000,
        y: 0,
    },
    direction_bits: 0xbfcb_4bc4,
    velocity: Vec2Bits {
        x: 0xbe56_74ba,
        y: 0xc13f_f884,
    },
    damage: 30,
    ..STRAIGHT
};

const SPREAD_RIGHT: BulletData = BulletData {
    motion: Vec2Bits {
        x: 0x4080_0000,
        y: 0,
    },
    direction_bits: 0xbfc6_d3f2,
    velocity: Vec2Bits {
        x: 0x3e56_7474,
        y: 0xc13f_f884,
    },
    damage: 30,
    ..STRAIGHT
};

const RANK1: [BulletData; 1] = [STRAIGHT];
const RANK2: [BulletData; 3] = [STRAIGHT, HOMING_LEFT, HOMING_RIGHT];
const RANK3: [BulletData; 4] = [SPREAD_LEFT, SPREAD_RIGHT, HOMING_LEFT, HOMING_RIGHT];

/// Executes the Reimu-A allocation and geometry projection of one callback.
///
/// The fixed velocity bit patterns are the observed results of the pinned
/// executable's `cos`/`sin` helpers and are deliberately not recomputed with a
/// host trigonometric library. Position additions use the integer PC24 model.
pub fn spawn_reimu_a(input: SpawnInput) -> Result<SpawnOutput, SpawnError> {
    if input.timer >= 30 {
        return Err(SpawnError::TimerOutOfRange(input.timer));
    }
    for (slot, state) in input.slot_states.iter().copied().enumerate() {
        if state > BULLET_STATE_COLLIDED {
            return Err(SpawnError::InvalidSlotState {
                slot: slot as u8,
                state,
            });
        }
    }

    let data: &[BulletData] = match input.current_power {
        0..=7 => &RANK1,
        8..=15 => &RANK2,
        16..=31 => &RANK3,
        power => return Err(SpawnError::UnsupportedPower(power)),
    };

    let mut output = SpawnOutput {
        slot_states: input.slot_states,
        allocations: [InitializedBullet::default(); MAX_REIMU_A_RANK3_BULLETS],
        allocation_count: 0,
    };
    let mut next_slot = 0_usize;
    for (bullet_data_index, bullet) in data.iter().enumerate() {
        if input.timer % bullet.wait != bullet.frame {
            continue;
        }
        let Some(slot) = (next_slot..PLAYER_BULLET_SLOTS)
            .find(|slot| output.slot_states[*slot] == BULLET_STATE_UNUSED)
        else {
            break;
        };
        next_slot = slot + 1;
        let source = match bullet.source_spawn_position_idx {
            0 => input.player_position,
            1 | 2 => input.orb_positions[usize::from(bullet.source_spawn_position_idx - 1)],
            value => return Err(SpawnError::InvalidSourcePosition(value)),
        };
        let carry = input.slot_carry[slot];
        let position = Vec3Bits {
            x: pc24::add(source.x, bullet.motion.x)?,
            y: pc24::add(source.y, bullet.motion.y)?,
            z: BULLET_Z_BITS,
        };
        output.allocations[usize::from(output.allocation_count)] = InitializedBullet {
            slot: slot as u8,
            bullet_data_index: bullet_data_index as u8,
            position,
            size: Vec3Bits {
                x: bullet.size.x,
                y: bullet.size.y,
                z: ONE_BITS,
            },
            velocity: bullet.velocity,
            sideways_motion_bits: carry.sideways_motion_bits,
            unk_134: Vec3Bits {
                x: carry.unk_134_x_bits,
                y: bullet.speed_bits,
                z: bullet.direction_bits,
            },
            timer_previous: POPUP_TIMER_PREVIOUS,
            timer_subframe_bits: ZERO_BITS,
            timer_current: 0,
            damage: bullet.damage,
            bullet_type: bullet.bullet_type,
            unk_152: carry.unk_152,
            stored_spawn_position_idx: carry.stored_spawn_position_idx,
            source_spawn_position_idx: bullet.source_spawn_position_idx,
            requested_anm_script: bullet.anm_script,
        };
        output.allocation_count += 1;
        output.slot_states[slot] = BULLET_STATE_FIRED;
    }
    Ok(output)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn base_input(power: u16, timer: u8) -> SpawnInput {
        SpawnInput {
            timer,
            current_power: power,
            player_position: Vec3Bits {
                x: 192.0_f32.to_bits(),
                y: 384.0_f32.to_bits(),
                z: 0.495_f32.to_bits(),
            },
            orb_positions: [
                Vec3Bits {
                    x: 168.0_f32.to_bits(),
                    y: 384.0_f32.to_bits(),
                    z: 0.49_f32.to_bits(),
                },
                Vec3Bits {
                    x: 216.0_f32.to_bits(),
                    y: 384.0_f32.to_bits(),
                    z: 0.49_f32.to_bits(),
                },
            ],
            slot_states: [0; PLAYER_BULLET_SLOTS],
            slot_carry: [SlotCarry::default(); PLAYER_BULLET_SLOTS],
        }
    }

    #[test]
    fn rank_boundaries_and_timer_gates_are_exact() {
        for power in 0..8 {
            assert_eq!(spawn_reimu_a(base_input(power, 0)).unwrap().allocation_count, 1);
        }
        assert_eq!(spawn_reimu_a(base_input(8, 0)).unwrap().allocation_count, 3);
        assert_eq!(spawn_reimu_a(base_input(15, 0)).unwrap().allocation_count, 3);
        assert_eq!(spawn_reimu_a(base_input(16, 0)).unwrap().allocation_count, 4);
        assert_eq!(spawn_reimu_a(base_input(31, 0)).unwrap().allocation_count, 4);
        assert_eq!(spawn_reimu_a(base_input(31, 1)).unwrap().allocation_count, 0);
        assert_eq!(spawn_reimu_a(base_input(31, 5)).unwrap().allocation_count, 2);
    }

    #[test]
    fn allocation_scans_low_slots_and_preserves_dormant_carry() {
        let mut input = base_input(16, 0);
        input.slot_states[0] = BULLET_STATE_FIRED;
        input.slot_states[2] = BULLET_STATE_COLLIDED;
        input.slot_carry[1] = SlotCarry {
            sideways_motion_bits: 7,
            unk_134_x_bits: 11,
            unk_152: -3,
            stored_spawn_position_idx: 9,
        };
        let output = spawn_reimu_a(input).unwrap();
        assert_eq!(output.allocation_count, 4);
        assert_eq!(output.allocations.map(|bullet| bullet.slot), [1, 3, 4, 5]);
        assert_eq!(output.allocations[0].sideways_motion_bits, 7);
        assert_eq!(output.allocations[0].unk_134.x, 11);
        assert_eq!(output.allocations[0].unk_152, -3);
        assert_eq!(output.allocations[0].stored_spawn_position_idx, 9);
        assert_eq!(output.allocations[0].position.x, 188.0_f32.to_bits());
        assert_eq!(output.allocations[1].position.x, 196.0_f32.to_bits());
    }

    #[test]
    fn full_pool_and_unsupported_inputs_fail_or_stop_explicitly() {
        let mut full = base_input(16, 0);
        full.slot_states = [BULLET_STATE_FIRED; PLAYER_BULLET_SLOTS];
        assert_eq!(spawn_reimu_a(full).unwrap().allocation_count, 0);
        assert_eq!(
            spawn_reimu_a(base_input(32, 0)),
            Err(SpawnError::UnsupportedPower(32))
        );
        assert_eq!(
            spawn_reimu_a(base_input(0, 30)),
            Err(SpawnError::TimerOutOfRange(30))
        );
    }
}
