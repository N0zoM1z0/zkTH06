#include <SDL2/SDL.h>
#include <SDL2/SDL_mouse.h>
#include <cstdio>

#include "AnmManager.hpp"
#include "Chain.hpp"
#include "FileSystem.hpp"
#include "GameErrorContext.hpp"
#include "GameManager.hpp"
#include "GameWindow.hpp"
#include "HeadlessRuntime.hpp"
#include "SoundPlayer.hpp"
#include "Stage.hpp"
#include "Supervisor.hpp"
#include "ZunResult.hpp"
#include "i18n.hpp"
#include "utils.hpp"

int main(int argc, char *argv[])
{
    if (!g_HeadlessRuntime.ParseArguments(argc, argv))
    {
        return 2;
    }
    if (g_HeadlessRuntime.replayInfoPath != NULL)
    {
        return g_HeadlessRuntime.PrintReplayInfo() ? 0 : 2;
    }
    if (g_HeadlessRuntime.canonicalSelfTest)
    {
        return g_HeadlessRuntime.RunCanonicalSelfTest() ? 0 : 2;
    }
    const bool headlessAtLaunch = g_HeadlessRuntime.enabled;
    if (!g_HeadlessRuntime.InitializeIo())
    {
        return 2;
    }
    g_HeadlessRuntime.ConfigureEnvironment();

    i32 renderResult = 0;
    //    MSG msg;
    //    i32 waste1, waste2, waste3, waste4, waste5, waste6;

    //    if (utils::CheckForRunningGameInstance())
    //    {
    //        g_GameErrorContext.Flush();
    //
    //        return 1;
    //    }

    //    g_Supervisor.hInstance = hInstance;

    if (g_Supervisor.LoadConfig(TH_CONFIG_FILE) != ZUN_SUCCESS)
    {
        g_GameErrorContext.Flush();
        return -1;
    }
    if (g_HeadlessRuntime.enabled)
    {
        g_Supervisor.cfg.musicMode = OFF;
        g_Supervisor.cfg.playSounds = 0;
        g_Supervisor.cfg.frameskipConfig = 0;
    }

    //    if (GameWindow::InitD3dInterface())
    //    {
    //        g_GameErrorContext.Flush();
    //        return 1;
    //    }

    //    SystemParametersInfo(SPI_GETSCREENSAVEACTIVE, 0, &g_GameWindow.screenSaveActive, 0);
    //    SystemParametersInfo(SPI_GETLOWPOWERACTIVE, 0, &g_GameWindow.lowPowerActive, 0);
    //    SystemParametersInfo(SPI_GETPOWEROFFACTIVE, 0, &g_GameWindow.powerOffActive, 0);
    //    SystemParametersInfo(SPI_SETSCREENSAVEACTIVE, 0, NULL, SPIF_SENDCHANGE);
    //    SystemParametersInfo(SPI_SETLOWPOWERACTIVE, 0, NULL, SPIF_SENDCHANGE);
    //    SystemParametersInfo(SPI_SETPOWEROFFACTIVE, 0, NULL, SPIF_SENDCHANGE);

restart:
    GameWindow::CreateGameWindow();

    g_AnmManager = new AnmManager();

    if (GameWindow::InitD3dRendering() != ZUN_SUCCESS)
    {
        g_GameErrorContext.Flush();
        return 1;
    }

    g_SoundPlayer.InitializeDSound();
    Controller::GetJoystickCaps();
    Controller::ResetKeyboard();

    if (Supervisor::RegisterChain() != ZUN_SUCCESS)
    {
        goto stop;
    }
    g_HeadlessRuntime.ConfigureDirectReplay();
    g_HeadlessRuntime.ConfigureDirectPractice();
    if (!g_Supervisor.cfg.windowed)
    {
        SDL_ShowCursor(SDL_DISABLE);
    }

    g_GameWindow.curFrame = 0;

    while (true)
    {
        SDL_Event e;

        while (SDL_PollEvent(&e))
        {
            if (e.type == SDL_QUIT)
            {
                goto stop;
            }
        }

        renderResult = g_GameWindow.Render();
        if (renderResult != 0)
        {
            break;
        }

        //        SDL_Delay(1000.0f / 60.0f);

        //        if (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE))
        //        {
        //            TranslateMessage(&msg);
        //            DispatchMessage(&msg);
        //        }
        //        else
        //        {
        //            testCoopLevelRes = g_Supervisor.d3dDevice->TestCooperativeLevel();
        //            if (testCoopLevelRes == D3D_OK)
        //            {
        //                renderResult = g_GameWindow.Render();
        //                if (renderResult != 0)
        //                {
        //                    goto stop;
        //                }
        //            }
        //            else if (testCoopLevelRes == D3DERR_DEVICENOTRESET)
        //            {
        //                g_AnmManager->ReleaseSurfaces();
        //                testResetRes = g_Supervisor.d3dDevice->Reset(&g_Supervisor.presentParameters);
        //                if (testResetRes != 0)
        //                {
        //                    goto stop;
        //                }
        //                GameWindow::InitD3dDevice();
        //                g_Supervisor.unk198 = 3;
        //            }
        //        }
    }

stop:
    g_Chain.Release();
    g_SoundPlayer.Release();
    g_HeadlessRuntime.CloseIo();

    delete g_AnmManager;
    g_AnmManager = NULL;

    if (g_GfxBackend != NULL)
        delete g_GfxBackend;
    SDL_Quit();

    if (renderResult == RENDER_RESULT_EXIT_ERROR && !headlessAtLaunch)
    {
        g_GameErrorContext.ResetContext();

        g_GameErrorContext.Log(TH_ERR_OPTION_CHANGED_RESTART);

        if (!g_Supervisor.cfg.windowed)
        {
            SDL_ShowCursor(SDL_ENABLE);
        }

        goto restart;
    }

    std::fprintf(stderr,
                 "TH06 runtime complete (headless=%d, ticks=%llu, terminal=%s, stage=%d, frame=%u, "
                 "score=%u, lives=%d, bombs=%d)\n",
                 headlessAtLaunch,
                 (unsigned long long)g_HeadlessRuntime.ticks,
                 g_HeadlessRuntime.terminalReason == NULL ? "none" : g_HeadlessRuntime.terminalReason,
                 g_GameManager.currentStage, g_GameManager.gameFrames, g_GameManager.score,
                 g_GameManager.livesRemaining, g_GameManager.bombsRemaining);
    if (!headlessAtLaunch)
    {
        FileSystem::WriteDataToFile(TH_CONFIG_FILE, &g_Supervisor.cfg, sizeof(g_Supervisor.cfg));
    }
    //    SystemParametersInfo(SPI_SETSCREENSAVEACTIVE, g_GameWindow.screenSaveActive, NULL, SPIF_SENDCHANGE);
    //    SystemParametersInfo(SPI_SETLOWPOWERACTIVE, g_GameWindow.lowPowerActive, NULL, SPIF_SENDCHANGE);
    //    SystemParametersInfo(SPI_SETPOWEROFFACTIVE, g_GameWindow.powerOffActive, NULL, SPIF_SENDCHANGE);

    SDL_ShowCursor(SDL_ENABLE);
    g_GameErrorContext.Flush();
    return headlessAtLaunch && (renderResult == RENDER_RESULT_EXIT_ERROR || g_HeadlessRuntime.outputError) ? 1 : 0;
}
