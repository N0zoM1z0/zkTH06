#pragma once

#include "Sha256.hpp"
#include "inttypes.hpp"

#include <array>
#include <cstddef>
#include <cstdio>

enum class CanonicalSubsystem : u16
{
    GLOBAL = 1,
    RNG = 2,
    PLAYER = 3,
    PLAYER_BULLETS = 4,
    ENEMIES_ECL = 5,
    ENEMY_BULLETS = 6,
    LASERS = 7,
    ITEMS = 8,
    STAGE = 9,
    GUI_MESSAGE = 10,
    EFFECTS = 11,
};

enum class CanonicalTerminalReason : u8
{
    NONE = 0,
    INPUT_ERROR = 1,
    PHYSICAL_HIT = 2,
    REPLAY_COMPLETE = 3,
    CHAIN_EXIT_SUCCESS = 4,
    CHAIN_EXIT_ERROR = 5,
    TICK_LIMIT = 6,
    UNKNOWN = 255,
};

enum class CanonicalRunMode : u8
{
    UNKNOWN = 0,
    PRACTICE = 1,
    REPLAY = 2,
};

struct CanonicalRunConfig
{
    u16 initialSeed = 0;
    u8 difficulty = 0;
    u8 character = 0;
    u8 shotType = 0;
    u8 startStage = 0;
    CanonicalRunMode mode = CanonicalRunMode::UNKNOWN;
};

struct CanonicalFrameMetadata
{
    u64 tick = 0;
    u32 gameFrame = 0;
    i32 stage = 0;
    u16 input = 0;
    CanonicalTerminalReason terminalReason = CanonicalTerminalReason::NONE;
    u8 flags = 0;
    i32 supervisorState = 0;
    u64 recordIndex = 0;
};

struct CanonicalSubsystemDigest
{
    CanonicalSubsystem subsystem = CanonicalSubsystem::GLOBAL;
    u16 flags = 0;
    u32 entityCount = 0;
    u64 byteCount = 0;
    Sha256Digest digest{};
};

constexpr size_t CANONICAL_SUBSYSTEM_COUNT = 11;
constexpr size_t CANONICAL_TRACE_HEADER_SIZE = 64;
constexpr size_t CANONICAL_TRACE_RECORD_PREFIX_SIZE = 32;
constexpr size_t CANONICAL_TRACE_SUBSYSTEM_RECORD_SIZE = 48;
constexpr size_t CANONICAL_TRACE_RECORD_SIZE =
    CANONICAL_TRACE_RECORD_PREFIX_SIZE + CANONICAL_SUBSYSTEM_COUNT * CANONICAL_TRACE_SUBSYSTEM_RECORD_SIZE + 32;

using CanonicalSubsystemDigests = std::array<CanonicalSubsystemDigest, CANONICAL_SUBSYSTEM_COUNT>;

class CanonicalSink
{
  public:
    explicit CanonicalSink(CanonicalSubsystem subsystem);

    void U8(u8 value);
    void I8(i8 value);
    void U16(u16 value);
    void I16(i16 value);
    void U32(u32 value);
    void I32(i32 value);
    void U64(u64 value);
    void F32(f32 value);
    void Boolean(bool value);
    void Bytes(const void *data, size_t size);

    CanonicalSubsystemDigest Finish(u16 flags, u32 entityCount);

  private:
    void Payload(const u8 *bytes, size_t size);

    CanonicalSubsystem subsystem;
    Sha256 hash;
    u64 byteCount = 0;
};

class CanonicalTrace
{
  public:
    static constexpr u16 VERSION_MAJOR = 0;
    static constexpr u16 VERSION_MINOR = 2;
    static constexpr u16 HEADER_FLAG_SELECTED_FIELDS = 1;
    static constexpr u16 SUBSYSTEM_FLAG_SELECTED_FIELDS = 1;

    static Sha256Digest SchemaDigest();
    static const char *SubsystemName(CanonicalSubsystem subsystem);
    static CanonicalTerminalReason ParseTerminalReason(const char *reason);

    static bool WriteHeader(FILE *file, const CanonicalRunConfig &config, char *error, size_t errorSize);
    static bool WriteRecord(FILE *file, const CanonicalFrameMetadata &frame,
                            const CanonicalSubsystemDigests &subsystems, char *error, size_t errorSize);
    static bool WriteTestFixture(const char *path, char *error, size_t errorSize);
    static bool SelfTest();
};
