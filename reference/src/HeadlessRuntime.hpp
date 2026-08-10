#pragma once

#include "inttypes.hpp"

#include <cstdio>

struct Player;

struct HeadlessPlayerBulletTrace
{
    u32 positionBits[3] = {};
    u32 sizeBits[3] = {};
    u32 velocityBits[2] = {};
    u32 sidewaysMotionBits = 0;
    u32 unk134Bits[3] = {};
    i32 timerPrevious = 0;
    u32 timerSubframeBits = 0;
    i32 timerCurrent = 0;
    i16 damage = 0;
    i16 state = 0;
    i16 type = 0;
    i16 unk152 = 0;
    i16 spawnPositionIdx = 0;
    u32 spritePositionBits[3] = {};
    i32 spriteTimerPrevious = 0;
    u32 spriteTimerSubframeBits = 0;
    i32 spriteTimerCurrent = 0;
    u32 spriteFlags = 0;
    i16 spriteActiveIndex = 0;
    i16 spriteAnmFileIndex = 0;
};

struct HeadlessPlayerSpawnTrace
{
    bool valid = false;
    bool returned = false;
    u32 timer = 0;
    u16 currentPower = 0;
    u8 isFocus = 0;
    u32 playerPositionBits[3] = {};
    u32 orbPositionBits[2][3] = {};
    HeadlessPlayerBulletTrace before[80] = {};
    HeadlessPlayerBulletTrace after[80] = {};
};

struct HeadlessRuntime
{
    bool enabled = false;
    bool seedProvided = false;
    u16 seed = 0;
    u16 actualSeed = 0;
    u64 maxTicks = 0;
    u64 ticks = 0;
    i32 practiceStage = 0;
    i32 difficulty = 1;
    i32 character = 0;
    i32 shotType = 0;
    bool autoShoot = false;
    bool stepMode = false;
    bool continueAfterHit = false;
    bool canonicalSelfTest = false;
    const char *actionsPath = NULL;
    const char *tracePath = NULL;
    const char *canonicalTracePath = NULL;
    const char *replayInfoPath = NULL;
    const char *replayPath = NULL;
    const char *canonicalSelfTestPath = NULL;
    i32 replayStartStage = 0;
    i8 replayInitialLives = 0;
    i8 replayInitialBombs = 0;
    FILE *actionsFile = NULL;
    FILE *traceFile = NULL;
    FILE *canonicalTraceFile = NULL;
    bool ownsActionsFile = false;
    bool ownsTraceFile = false;
    bool ownsCanonicalTraceFile = false;
    bool canonicalHeaderWritten = false;
    bool outputError = false;
    u64 canonicalRecords = 0;
    u64 actionRepeatsRemaining = 0;
    u16 repeatedAction = 0;
    bool inputReady = false;
    bool inputError = false;
    const char *terminalReason = NULL;
    HeadlessPlayerSpawnTrace playerSpawnTrace;

    bool ParseArguments(int argc, char *argv[]);
    bool PrintReplayInfo() const;
    bool RunCanonicalSelfTest() const;
    bool PrepareReplay();
    void ConfigureEnvironment() const;
    bool InitializeIo();
    void CloseIo();
    void ConfigureDirectPractice();
    void ConfigureDirectReplay();
    u16 NextInput();
    void WriteState(const char *terminalReason);
    void BeginPlayerSpawnTrace(const Player *player, u32 timer);
    void EndPlayerSpawnTrace(const Player *player);
    bool WriteCanonicalState(const char *terminalReason);
    bool ShouldStopForHit() const;
    bool IsReplayComplete() const;
    bool AdvanceTick();
};

extern HeadlessRuntime g_HeadlessRuntime;
