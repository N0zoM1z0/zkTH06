#include "ReplayFile.hpp"

#include "Controller.hpp"
#include "FileSystem.hpp"
#include "Supervisor.hpp"
#include "utils.hpp"

#include <bit>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace
{
constexpr u32 REPLAY_CHECKSUM_SEED = 0x3f000318;
constexpr i32 REPLAY_END_FRAME = 9'999'999;
constexpr u16 REPLAY_INPUT_MASK =
    TH_BUTTON_SHOOT | TH_BUTTON_BOMB | TH_BUTTON_FOCUS | TH_BUTTON_SKIP | TH_BUTTON_DIRECTION;

void SetError(char *error, size_t errorSize, const char *format, ...)
{
    if (error == NULL || errorSize == 0)
    {
        return;
    }
    va_list args;
    va_start(args, format);
    std::vsnprintf(error, errorSize, format, args);
    va_end(args);
}
} // namespace

static_assert(std::endian::native == std::endian::little, "TH06 replay files require little-endian decoding");

ReplayFile::~ReplayFile()
{
    this->Reset();
}

void ReplayFile::Reset()
{
    std::free(this->bytes);
    this->bytes = NULL;
    this->size = 0;
    this->header = NULL;
    for (ReplayStageView &stage : this->stages)
    {
        stage = {};
    }
}

bool ReplayFile::LoadExternal(const char *path, char *error, size_t errorSize)
{
    this->Reset();
    if (path == NULL || path[0] == '\0')
    {
        SetError(error, errorSize, "replay path is empty");
        return false;
    }

    u8 *fileData = FileSystem::OpenPath(path, 1);
    if (fileData == NULL)
    {
        SetError(error, errorSize, "could not open replay: %s", path);
        return false;
    }
    return this->AdoptAndValidate(fileData, g_LastFileSize, error, errorSize);
}

bool ReplayFile::AdoptAndValidate(u8 *fileData, size_t fileSize, char *error, size_t errorSize)
{
    this->bytes = fileData;
    this->size = fileSize;

    if (fileSize < sizeof(ReplayHeader))
    {
        SetError(error, errorSize, "replay is too short: %zu bytes", fileSize);
        this->Reset();
        return false;
    }

    this->header = reinterpret_cast<ReplayHeader *>(this->bytes);
    if (std::memcmp(this->header->magic, "T6RP", 4) != 0)
    {
        SetError(error, errorSize, "invalid replay magic");
        this->Reset();
        return false;
    }

    u8 transform = static_cast<u8>(this->header->key);
    for (size_t cursor = offsetof(ReplayHeader, rngValue3); cursor < fileSize; cursor++)
    {
        this->bytes[cursor] = static_cast<u8>(this->bytes[cursor] - transform);
        transform = static_cast<u8>(transform + 7);
    }

    u32 checksum = REPLAY_CHECKSUM_SEED;
    for (size_t cursor = offsetof(ReplayHeader, key); cursor < fileSize; cursor++)
    {
        checksum += this->bytes[cursor];
    }
    if (checksum != static_cast<u32>(this->header->checksum))
    {
        SetError(error, errorSize, "replay checksum mismatch: expected %08x, calculated %08x",
                 static_cast<u32>(this->header->checksum), checksum);
        this->Reset();
        return false;
    }
    if (this->header->version != GAME_VERSION)
    {
        SetError(error, errorSize, "unsupported replay version: %04x", static_cast<unsigned>(this->header->version));
        this->Reset();
        return false;
    }
    if (this->header->shottypeChara > 3)
    {
        SetError(error, errorSize, "invalid replay character/shot index: %u",
                 static_cast<unsigned>(this->header->shottypeChara));
        this->Reset();
        return false;
    }
    if (this->header->difficulty > 4)
    {
        SetError(error, errorSize, "invalid replay difficulty: %u",
                 static_cast<unsigned>(this->header->difficulty));
        this->Reset();
        return false;
    }

    size_t previousOffset = 0;
    size_t populatedStages = 0;
    for (size_t index = 0; index < ARRAY_SIZE(this->stages); index++)
    {
        const size_t start = this->header->stageReplayDataOffsets[index];
        if (start == 0)
        {
            continue;
        }
        if (start < sizeof(ReplayHeader) || start >= fileSize || start % alignof(ReplayDataInput) != 0)
        {
            SetError(error, errorSize, "stage %zu has invalid offset: %zu", index + 1, start);
            this->Reset();
            return false;
        }
        if (previousOffset != 0 && start <= previousOffset)
        {
            SetError(error, errorSize, "stage offsets are not strictly increasing at stage %zu", index + 1);
            this->Reset();
            return false;
        }
        previousOffset = start;
        populatedStages++;
    }
    if (populatedStages == 0)
    {
        SetError(error, errorSize, "replay contains no stage data");
        this->Reset();
        return false;
    }

    for (size_t index = 0; index < ARRAY_SIZE(this->stages); index++)
    {
        const size_t start = this->header->stageReplayDataOffsets[index];
        if (start == 0)
        {
            continue;
        }

        size_t end = fileSize;
        for (size_t next = index + 1; next < ARRAY_SIZE(this->stages); next++)
        {
            if (this->header->stageReplayDataOffsets[next] != 0)
            {
                end = this->header->stageReplayDataOffsets[next];
                break;
            }
        }
        const size_t stageHeaderSize = offsetof(StageReplayData, replayInputs);
        if (end <= start || end - start < stageHeaderSize + 2 * sizeof(ReplayDataInput) ||
            (end - start - stageHeaderSize) % sizeof(ReplayDataInput) != 0)
        {
            SetError(error, errorSize, "stage %zu has invalid byte size: %zu", index + 1, end - start);
            this->Reset();
            return false;
        }

        ReplayStageView &stage = this->stages[index];
        stage.data = reinterpret_cast<StageReplayData *>(this->bytes + start);
        stage.inputs = reinterpret_cast<ReplayDataInput *>(this->bytes + start + stageHeaderSize);
        stage.fileOffset = start;
        stage.byteSize = end - start;
        stage.inputRecordCount = (stage.byteSize - stageHeaderSize) / sizeof(ReplayDataInput);

        if (stage.inputs[0].frameNum != 0)
        {
            SetError(error, errorSize, "stage %zu does not start with frame 0", index + 1);
            this->Reset();
            return false;
        }

        i32 previousFrame = stage.inputs[0].frameNum;
        bool foundSentinel = false;
        for (size_t record = 0; record < stage.inputRecordCount; record++)
        {
            const ReplayDataInput &input = stage.inputs[record];
            if ((input.inputKey & ~REPLAY_INPUT_MASK) != 0)
            {
                SetError(error, errorSize, "stage %zu record %zu has invalid input mask: %04x", index + 1,
                         record, static_cast<unsigned>(input.inputKey));
                this->Reset();
                return false;
            }
            if (input.frameNum == REPLAY_END_FRAME)
            {
                if (input.inputKey != 0 || record == 0)
                {
                    SetError(error, errorSize, "stage %zu has malformed end sentinel", index + 1);
                    this->Reset();
                    return false;
                }
                stage.playbackRecordCount = record + 1;
                stage.terminalFrame = stage.inputs[record - 1].frameNum;
                foundSentinel = true;
                break;
            }
            if (input.frameNum < 0 || input.frameNum < previousFrame)
            {
                SetError(error, errorSize, "stage %zu input frames regress at record %zu", index + 1, record);
                this->Reset();
                return false;
            }
            previousFrame = input.frameNum;
        }
        if (!foundSentinel)
        {
            SetError(error, errorSize, "stage %zu has no playback end sentinel", index + 1);
            this->Reset();
            return false;
        }
    }

    if (error != NULL && errorSize != 0)
    {
        error[0] = '\0';
    }
    return true;
}
