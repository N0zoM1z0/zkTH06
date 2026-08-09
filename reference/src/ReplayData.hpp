#pragma once

#include "inttypes.hpp"

#include <cstddef>

struct ReplayDataInput
{
    i32 frameNum;
    u16 inputKey;
    u16 padding;
};

struct StageReplayData
{
    i32 score;
    i16 randomSeed;
    i16 pointItemsCollected;
    u8 power;
    i8 livesRemaining;
    i8 bombsRemaining;
    u8 rank;
    i8 powerItemCountForScore;
    i8 padding[3];
    ReplayDataInput replayInputs[53998];
};

struct ReplayHeader
{
    char magic[4];
    u16 version;
    u8 shottypeChara;
    u8 difficulty;
    i32 checksum;
    u8 rngValue1;
    u8 rngValue2;
    i8 key;
    i8 rngValue3;
    char date[9];
    char name[8];
    i32 score;
    f32 slowdownRate2;
    f32 slowdownRate;
    f32 slowdownRate3;
    u32 stageReplayDataOffsets[7];
};

struct ReplayData
{
    ReplayHeader *header;
    StageReplayData *stageReplayData[7];
};

static_assert(sizeof(ReplayDataInput) == 0x8);
static_assert(sizeof(ReplayHeader) == 0x50);
static_assert(offsetof(ReplayHeader, key) == 0x0e);
static_assert(offsetof(ReplayHeader, rngValue3) == 0x0f);
static_assert(offsetof(ReplayHeader, stageReplayDataOffsets) == 0x34);
static_assert(offsetof(StageReplayData, replayInputs) == 0x10);
