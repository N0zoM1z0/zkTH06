#pragma once

#include "Chain.hpp"
#include "ChainPriorities.hpp"
#include "ReplayData.hpp"
#include "inttypes.hpp"

class ReplayFile;

struct ReplayManager
{
    static ZunResult RegisterChain(i32 isDemo, const char *replayFile);
    static ChainCallbackResult OnUpdate(ReplayManager *mgr);
    static ChainCallbackResult OnUpdateDemoHighPrio(ReplayManager *mgr);
    static ChainCallbackResult OnUpdateDemoLowPrio(ReplayManager *mgr);
    static ChainCallbackResult OnDraw(ReplayManager *mgr);
    static ZunResult AddedCallback(ReplayManager *mgr);
    static ZunResult AddedCallbackDemo(ReplayManager *mgr);
    static ZunResult DeletedCallback(ReplayManager *mgr);
    static void StopRecording();
    static void SaveReplay(const char *replay_path, char *param_2);
    static ZunResult ValidateReplayData(const ReplayHeader *data, i32 fileSize);

    ReplayManager() = default;

    i32 IsDemo() const
    {
        return this->isDemo;
    }

    i32 frameId = 0;
    ReplayData *replayData = NULL;
    i32 isDemo = 0;
    const char *replayFile = NULL;
    u8 unk10[52] = {};
    u16 unk44 = 0;
    ReplayDataInput *replayInputs = NULL;
    ReplayDataInput *replayInputEnd = NULL;
    const ReplayDataInput *replayInputStageBookmarks[7] = {};
    ChainElem *calcChain = NULL;
    ChainElem *drawChain = NULL;
    ChainElem *calcChainDemoHighPrio = NULL;
    ReplayFile *loadedReplay = NULL;
};
