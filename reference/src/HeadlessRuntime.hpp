#pragma once

#include "inttypes.hpp"

#include <cstdio>

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
    const char *replayInfoPath = NULL;
    const char *replayPath = NULL;
    i32 replayStartStage = 0;
    i8 replayInitialLives = 0;
    i8 replayInitialBombs = 0;
    FILE *actionsFile = NULL;
    FILE *traceFile = NULL;
    bool ownsActionsFile = false;
    bool ownsTraceFile = false;
    u64 actionRepeatsRemaining = 0;
    u16 repeatedAction = 0;
    bool inputReady = false;
    bool inputError = false;
    const char *terminalReason = NULL;

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
    bool ShouldStopForHit() const;
    bool IsReplayComplete() const;
    bool AdvanceTick();
};

extern HeadlessRuntime g_HeadlessRuntime;
