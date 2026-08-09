#pragma once

#include "ReplayData.hpp"

#include <cstddef>

struct ReplayStageView
{
    StageReplayData *data = NULL;
    ReplayDataInput *inputs = NULL;
    size_t fileOffset = 0;
    size_t byteSize = 0;
    size_t inputRecordCount = 0;
    size_t playbackRecordCount = 0;
    i32 terminalFrame = 0;
};

// Owns one decoded replay file and exposes bounds-checked stage views.  The
// game's byte transform is reversible obfuscation, not authentication.
class ReplayFile
{
  public:
    ReplayFile() = default;
    ~ReplayFile();

    ReplayFile(const ReplayFile &) = delete;
    ReplayFile &operator=(const ReplayFile &) = delete;

    bool LoadExternal(const char *path, char *error, size_t errorSize);
    bool LoadPath(const char *path, bool external, char *error, size_t errorSize);
    void Reset();

    ReplayHeader *Header()
    {
        return this->header;
    }

    const ReplayHeader *Header() const
    {
        return this->header;
    }

    size_t Size() const
    {
        return this->size;
    }

    const ReplayStageView &Stage(size_t index) const
    {
        return this->stages[index];
    }

  private:
    bool AdoptAndValidate(u8 *fileData, size_t fileSize, char *error, size_t errorSize);

    u8 *bytes = NULL;
    size_t size = 0;
    ReplayHeader *header = NULL;
    ReplayStageView stages[7] = {};
};
