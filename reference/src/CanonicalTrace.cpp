#include "CanonicalTrace.hpp"

#include <cerrno>
#include <cstring>

namespace
{
constexpr u8 TRACE_MAGIC[8] = {'Z', 'K', 'T', 'H', '0', '6', 'C', 'T'};
constexpr char SCHEMA_DESCRIPTOR[] =
    "zkTH06 canonical trace schema 0.1\n"
    "wire=little-endian;float=ieee754-binary32-raw-bits;coverage=selected-fields\n"
    "subsystems=global,rng,player,player-bullets,enemies-ecl,enemy-bullets,lasers,items,stage,gui-message,effects\n"
    "subsystem-digest=sha256(zkTH06-state-v0.1\\0||subsystem-u16-le||payload)\n"
    "record-root=sha256(zkTH06-trace-root-v0.1\\0||record-prefix||subsystem-records)\n";
constexpr char STATE_DOMAIN[] = "zkTH06-state-v0.1\0";
constexpr char ROOT_DOMAIN[] = "zkTH06-trace-root-v0.1\0";

void SetError(char *error, size_t errorSize, const char *message)
{
    if (error != NULL && errorSize != 0)
    {
        std::snprintf(error, errorSize, "%s", message);
    }
}

class WireBuffer
{
  public:
    WireBuffer(u8 *bytes, size_t capacity) : bytes(bytes), capacity(capacity)
    {
    }

    bool U8(u8 value)
    {
        return this->Append(&value, 1);
    }

    bool U16(u16 value)
    {
        const u8 encoded[2] = {static_cast<u8>(value), static_cast<u8>(value >> 8)};
        return this->Append(encoded, sizeof(encoded));
    }

    bool U32(u32 value)
    {
        const u8 encoded[4] = {static_cast<u8>(value), static_cast<u8>(value >> 8), static_cast<u8>(value >> 16),
                               static_cast<u8>(value >> 24)};
        return this->Append(encoded, sizeof(encoded));
    }

    bool I32(i32 value)
    {
        return this->U32(static_cast<u32>(value));
    }

    bool U64(u64 value)
    {
        u8 encoded[8];
        for (size_t index = 0; index < sizeof(encoded); index++)
        {
            encoded[index] = static_cast<u8>(value >> (index * 8));
        }
        return this->Append(encoded, sizeof(encoded));
    }

    bool Bytes(const void *data, size_t size)
    {
        return this->Append(static_cast<const u8 *>(data), size);
    }

    size_t Size() const
    {
        return this->size;
    }

  private:
    bool Append(const u8 *data, size_t count)
    {
        if (count > this->capacity - this->size)
        {
            return false;
        }
        std::memcpy(this->bytes + this->size, data, count);
        this->size += count;
        return true;
    }

    u8 *bytes;
    size_t capacity;
    size_t size = 0;
};

bool WriteAll(FILE *file, const void *data, size_t size, char *error, size_t errorSize)
{
    if (file == NULL)
    {
        SetError(error, errorSize, "canonical trace file is null");
        return false;
    }
    if (std::fwrite(data, 1, size, file) != size)
    {
        SetError(error, errorSize, "failed to write canonical trace");
        return false;
    }
    return true;
}

CanonicalSubsystem ExpectedSubsystem(size_t index)
{
    return static_cast<CanonicalSubsystem>(index + 1);
}
} // namespace

CanonicalSink::CanonicalSink(CanonicalSubsystem subsystem) : subsystem(subsystem)
{
    this->hash.Update(STATE_DOMAIN, sizeof(STATE_DOMAIN) - 1);
    const u16 id = static_cast<u16>(subsystem);
    const u8 encoded[2] = {static_cast<u8>(id), static_cast<u8>(id >> 8)};
    this->hash.Update(encoded, sizeof(encoded));
}

void CanonicalSink::Payload(const u8 *bytes, size_t size)
{
    this->hash.Update(bytes, size);
    this->byteCount += size;
}

void CanonicalSink::U8(u8 value)
{
    this->Payload(&value, 1);
}

void CanonicalSink::I8(i8 value)
{
    this->U8(static_cast<u8>(value));
}

void CanonicalSink::U16(u16 value)
{
    const u8 encoded[2] = {static_cast<u8>(value), static_cast<u8>(value >> 8)};
    this->Payload(encoded, sizeof(encoded));
}

void CanonicalSink::I16(i16 value)
{
    this->U16(static_cast<u16>(value));
}

void CanonicalSink::U32(u32 value)
{
    const u8 encoded[4] = {static_cast<u8>(value), static_cast<u8>(value >> 8), static_cast<u8>(value >> 16),
                           static_cast<u8>(value >> 24)};
    this->Payload(encoded, sizeof(encoded));
}

void CanonicalSink::I32(i32 value)
{
    this->U32(static_cast<u32>(value));
}

void CanonicalSink::U64(u64 value)
{
    u8 encoded[8];
    for (size_t index = 0; index < sizeof(encoded); index++)
    {
        encoded[index] = static_cast<u8>(value >> (index * 8));
    }
    this->Payload(encoded, sizeof(encoded));
}

void CanonicalSink::F32(f32 value)
{
    u32 bits;
    static_assert(sizeof(bits) == sizeof(value));
    std::memcpy(&bits, &value, sizeof(bits));
    this->U32(bits);
}

void CanonicalSink::Boolean(bool value)
{
    this->U8(value ? 1 : 0);
}

void CanonicalSink::Bytes(const void *data, size_t size)
{
    this->Payload(static_cast<const u8 *>(data), size);
}

CanonicalSubsystemDigest CanonicalSink::Finish(u16 flags, u32 entityCount)
{
    CanonicalSubsystemDigest result;
    result.subsystem = this->subsystem;
    result.flags = flags;
    result.entityCount = entityCount;
    result.byteCount = this->byteCount;
    result.digest = this->hash.Finish();
    return result;
}

Sha256Digest CanonicalTrace::SchemaDigest()
{
    return Sha256::Hash(SCHEMA_DESCRIPTOR, sizeof(SCHEMA_DESCRIPTOR) - 1);
}

const char *CanonicalTrace::SubsystemName(CanonicalSubsystem subsystem)
{
    static constexpr const char *NAMES[CANONICAL_SUBSYSTEM_COUNT] = {
        "global",        "rng",           "player", "player-bullets", "enemies-ecl", "enemy-bullets",
        "lasers",        "items",         "stage",  "gui-message",    "effects",
    };
    const u16 id = static_cast<u16>(subsystem);
    return id >= 1 && id <= CANONICAL_SUBSYSTEM_COUNT ? NAMES[id - 1] : "unknown";
}

CanonicalTerminalReason CanonicalTrace::ParseTerminalReason(const char *reason)
{
    if (reason == NULL)
    {
        return CanonicalTerminalReason::NONE;
    }
    struct Mapping
    {
        const char *name;
        CanonicalTerminalReason value;
    };
    static constexpr Mapping MAPPINGS[] = {
        {"input-error", CanonicalTerminalReason::INPUT_ERROR},
        {"physical-hit", CanonicalTerminalReason::PHYSICAL_HIT},
        {"replay-complete", CanonicalTerminalReason::REPLAY_COMPLETE},
        {"chain-exit-success", CanonicalTerminalReason::CHAIN_EXIT_SUCCESS},
        {"chain-exit-error", CanonicalTerminalReason::CHAIN_EXIT_ERROR},
        {"tick-limit", CanonicalTerminalReason::TICK_LIMIT},
    };
    for (const Mapping &mapping : MAPPINGS)
    {
        if (std::strcmp(reason, mapping.name) == 0)
        {
            return mapping.value;
        }
    }
    return CanonicalTerminalReason::UNKNOWN;
}

bool CanonicalTrace::WriteHeader(FILE *file, const CanonicalRunConfig &config, char *error, size_t errorSize)
{
    std::array<u8, CANONICAL_TRACE_HEADER_SIZE> bytes{};
    WireBuffer wire(bytes.data(), bytes.size());
    const Sha256Digest schemaDigest = CanonicalTrace::SchemaDigest();
    const bool encoded = wire.Bytes(TRACE_MAGIC, sizeof(TRACE_MAGIC)) && wire.U16(VERSION_MAJOR) &&
                         wire.U16(VERSION_MINOR) && wire.U32(CANONICAL_TRACE_HEADER_SIZE) &&
                         wire.U32(CANONICAL_TRACE_RECORD_SIZE) && wire.U16(CANONICAL_SUBSYSTEM_COUNT) &&
                         wire.U16(HEADER_FLAG_SELECTED_FIELDS) && wire.U16(config.initialSeed) &&
                         wire.U8(config.difficulty) && wire.U8(config.character) && wire.U8(config.shotType) &&
                         wire.U8(config.startStage) && wire.U8(static_cast<u8>(config.mode)) && wire.U8(0) &&
                         wire.Bytes(schemaDigest.data(), schemaDigest.size());
    if (!encoded || wire.Size() != bytes.size())
    {
        SetError(error, errorSize, "internal canonical header size mismatch");
        return false;
    }
    return WriteAll(file, bytes.data(), bytes.size(), error, errorSize);
}

bool CanonicalTrace::WriteRecord(FILE *file, const CanonicalFrameMetadata &frame,
                                 const CanonicalSubsystemDigests &subsystems, char *error, size_t errorSize)
{
    std::array<u8, CANONICAL_TRACE_RECORD_SIZE> bytes{};
    WireBuffer wire(bytes.data(), bytes.size());
    bool encoded = wire.U64(frame.tick) && wire.U32(frame.gameFrame) && wire.I32(frame.stage) &&
                   wire.U16(frame.input) && wire.U8(static_cast<u8>(frame.terminalReason)) && wire.U8(frame.flags) &&
                   wire.I32(frame.supervisorState) && wire.U64(frame.recordIndex);
    for (size_t index = 0; encoded && index < subsystems.size(); index++)
    {
        const CanonicalSubsystemDigest &subsystem = subsystems[index];
        if (subsystem.subsystem != ExpectedSubsystem(index))
        {
            SetError(error, errorSize, "canonical subsystem order mismatch");
            return false;
        }
        encoded = wire.U16(static_cast<u16>(subsystem.subsystem)) && wire.U16(subsystem.flags) &&
                  wire.U32(subsystem.entityCount) && wire.U64(subsystem.byteCount) &&
                  wire.Bytes(subsystem.digest.data(), subsystem.digest.size());
    }
    if (!encoded || wire.Size() != CANONICAL_TRACE_RECORD_SIZE - 32)
    {
        SetError(error, errorSize, "internal canonical record size mismatch");
        return false;
    }

    Sha256 root;
    root.Update(ROOT_DOMAIN, sizeof(ROOT_DOMAIN) - 1);
    root.Update(bytes.data(), wire.Size());
    const Sha256Digest rootDigest = root.Finish();
    encoded = wire.Bytes(rootDigest.data(), rootDigest.size());
    if (!encoded || wire.Size() != bytes.size())
    {
        SetError(error, errorSize, "internal canonical root size mismatch");
        return false;
    }
    return WriteAll(file, bytes.data(), bytes.size(), error, errorSize);
}

bool CanonicalTrace::WriteTestFixture(const char *path, char *error, size_t errorSize)
{
    FILE *file = std::fopen(path, "wb");
    if (file == NULL)
    {
        if (error != NULL && errorSize != 0)
        {
            std::snprintf(error, errorSize, "cannot open canonical fixture: %s", std::strerror(errno));
        }
        return false;
    }

    CanonicalRunConfig config;
    config.initialSeed = 0x1234;
    config.difficulty = 2;
    config.character = 1;
    config.shotType = 0;
    config.startStage = 4;
    config.mode = CanonicalRunMode::REPLAY;

    CanonicalSubsystemDigests subsystems;
    for (size_t index = 0; index < subsystems.size(); index++)
    {
        const CanonicalSubsystem id = ExpectedSubsystem(index);
        CanonicalSink sink(id);
        sink.U32(static_cast<u32>(0x10203040 + index));
        sink.F32(static_cast<f32>(index) + 0.5f);
        subsystems[index] = sink.Finish(SUBSYSTEM_FLAG_SELECTED_FIELDS, static_cast<u32>(index + 1));
    }

    CanonicalFrameMetadata frame;
    frame.tick = 0x0102030405060708;
    frame.gameFrame = 12345;
    frame.stage = 4;
    frame.input = 0x55aa;
    frame.terminalReason = CanonicalTerminalReason::TICK_LIMIT;
    frame.flags = 3;
    frame.supervisorState = 7;
    frame.recordIndex = 0;

    bool result = CanonicalTrace::WriteHeader(file, config, error, errorSize) &&
                  CanonicalTrace::WriteRecord(file, frame, subsystems, error, errorSize);
    if (std::fclose(file) != 0 && result)
    {
        SetError(error, errorSize, "failed to close canonical fixture");
        result = false;
    }
    return result;
}

bool CanonicalTrace::SelfTest()
{
    if (!Sha256::SelfTest() || CANONICAL_TRACE_RECORD_SIZE != 592)
    {
        return false;
    }

    CanonicalSink first(CanonicalSubsystem::GLOBAL);
    first.U8(1);
    first.U16(0x0302);
    first.U32(0x07060504);
    first.F32(1.0f);
    const CanonicalSubsystemDigest digest1 = first.Finish(SUBSYSTEM_FLAG_SELECTED_FIELDS, 1);

    const u8 expectedPayload[] = {1, 2, 3, 4, 5, 6, 7, 0, 0, 0x80, 0x3f};
    CanonicalSink second(CanonicalSubsystem::GLOBAL);
    second.Bytes(expectedPayload, sizeof(expectedPayload));
    const CanonicalSubsystemDigest digest2 = second.Finish(SUBSYSTEM_FLAG_SELECTED_FIELDS, 1);
    return digest1.byteCount == sizeof(expectedPayload) && digest1.digest == digest2.digest;
}
