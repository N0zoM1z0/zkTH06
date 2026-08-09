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
    const char *actionsPath = NULL;
    const char *tracePath = NULL;
    const char *replayInfoPath = NULL;
    FILE *actionsFile = NULL;
    FILE *traceFile = NULL;
    bool ownsActionsFile = false;
    bool ownsTraceFile = false;
    u64 actionRepeatsRemaining = 0;
    u16 repeatedAction = 0;
    bool inputReady = false;
    bool inputError = false;

    bool ParseArguments(int argc, char *argv[]);
    bool PrintReplayInfo() const;
    void ConfigureEnvironment() const;
    bool InitializeIo();
    void CloseIo();
    void ConfigureDirectPractice();
    u16 NextInput();
    void WriteState(const char *terminalReason);
    bool ShouldStopForHit() const;
    bool AdvanceTick();
};

extern HeadlessRuntime g_HeadlessRuntime;
