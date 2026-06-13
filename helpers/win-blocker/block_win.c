#include <windows.h>

HHOOK hHook = NULL;

// Hook procedure
LRESULT CALLBACK LowLevelKeyboardProc(int nCode, WPARAM wParam, LPARAM lParam) {
    if (nCode == HC_ACTION) {
        KBDLLHOOKSTRUCT *pKeyBoard = (KBDLLHOOKSTRUCT *)lParam;
        
        // VK_LWIN (0x5B) - Left Win, VK_RWIN (0x5C) - Right Win
        if (pKeyBoard->vkCode == VK_LWIN || pKeyBoard->vkCode == VK_RWIN) {
            // Return 1 to block the key press from propagating further
            return 1;
        }
    }
    // If it is not Win, pass control further down the chain
    return CallNextHookEx(hHook, nCode, wParam, lParam);
}

int APIENTRY WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    // Install a global keyboard hook
    hHook = SetWindowsHookEx(WH_KEYBOARD_LL, LowLevelKeyboardProc, hInstance, 0);

    if (hHook == NULL) {
        return 1; // Failed to install the hook
    }

    // Windows message loop required for the hook to function
    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    // Remove the hook on exit (although the prefix will terminate the process itself)
    UnhookWindowsHookEx(hHook);
    return 0;
}
