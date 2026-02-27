Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# ═══════════════════════════════════════════════════════════════
# GLOBAL KEYBOARD HOOK (ESC detection even when form is minimized)
# ═══════════════════════════════════════════════════════════════
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Diagnostics;

public class GlobalKeyboardHook {
    private delegate IntPtr LowLevelKeyboardProc(int nCode, IntPtr wParam, IntPtr lParam);
    
    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr SetWindowsHookEx(int idHook, LowLevelKeyboardProc lpfn, IntPtr hMod, uint dwThreadId);
    
    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool UnhookWindowsHookEx(IntPtr hhk);
    
    [DllImport("user32.dll")]
    private static extern IntPtr CallNextHookEx(IntPtr hhk, int nCode, IntPtr wParam, IntPtr lParam);
    
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr GetModuleHandle(string lpModuleName);
    
    private const int WH_KEYBOARD_LL = 13;
    private const int WM_KEYDOWN = 0x0100;
    private const int VK_ESCAPE = 0x1B;
    private const int VK_PAUSE = 0x13;
    
    private static IntPtr hookId = IntPtr.Zero;
    private static LowLevelKeyboardProc proc;
    public static bool EscapePressed = false;
    public static bool PausePressed = false;
    
    public static void Install() {
        proc = HookCallback;
        using (Process curProcess = Process.GetCurrentProcess())
        using (ProcessModule curModule = curProcess.MainModule) {
            hookId = SetWindowsHookEx(WH_KEYBOARD_LL, proc, GetModuleHandle(curModule.ModuleName), 0);
        }
    }
    
    public static void Uninstall() {
        if (hookId != IntPtr.Zero) {
            UnhookWindowsHookEx(hookId);
            hookId = IntPtr.Zero;
        }
    }
    
    private static IntPtr HookCallback(int nCode, IntPtr wParam, IntPtr lParam) {
        if (nCode >= 0 && wParam == (IntPtr)WM_KEYDOWN) {
            int vkCode = Marshal.ReadInt32(lParam);
            if (vkCode == VK_ESCAPE) EscapePressed = true;
            if (vkCode == VK_PAUSE) PausePressed = true;
        }
        return CallNextHookEx(hookId, nCode, wParam, lParam);
    }
    
    public static void Reset() {
        EscapePressed = false;
        PausePressed = false;
    }
}
"@

# ═══════════════════════════════════════════════════════════════
# THEME & STYLING SYSTEM
# ═══════════════════════════════════════════════════════════════
$script:Themes = @{
    Dark = @{
        FormBack       = [System.Drawing.Color]::FromArgb(30, 30, 30)
        PanelBack      = [System.Drawing.Color]::FromArgb(40, 40, 40)
        CardBack       = [System.Drawing.Color]::FromArgb(50, 50, 50)
        TextPrimary    = [System.Drawing.Color]::FromArgb(240, 240, 240)
        TextSecondary  = [System.Drawing.Color]::FromArgb(160, 160, 160)
        TextMuted      = [System.Drawing.Color]::FromArgb(100, 100, 100)
        Accent         = [System.Drawing.Color]::FromArgb(0, 150, 255)
        AccentHover    = [System.Drawing.Color]::FromArgb(30, 170, 255)
        Success        = [System.Drawing.Color]::FromArgb(0, 200, 83)
        Warning        = [System.Drawing.Color]::FromArgb(255, 171, 0)
        Danger         = [System.Drawing.Color]::FromArgb(255, 69, 58)
        Border         = [System.Drawing.Color]::FromArgb(70, 70, 70)
        InputBack      = [System.Drawing.Color]::FromArgb(35, 35, 35)
        SliderBack     = [System.Drawing.Color]::FromArgb(60, 60, 60)
        StatusBar      = [System.Drawing.Color]::FromArgb(25, 25, 25)
        MenuBack       = [System.Drawing.Color]::FromArgb(45, 45, 45)
    }
    Light = @{
        FormBack       = [System.Drawing.Color]::FromArgb(243, 243, 243)
        PanelBack      = [System.Drawing.Color]::FromArgb(255, 255, 255)
        CardBack       = [System.Drawing.Color]::FromArgb(249, 249, 249)
        TextPrimary    = [System.Drawing.Color]::FromArgb(30, 30, 30)
        TextSecondary  = [System.Drawing.Color]::FromArgb(100, 100, 100)
        TextMuted      = [System.Drawing.Color]::FromArgb(160, 160, 160)
        Accent         = [System.Drawing.Color]::FromArgb(0, 120, 212)
        AccentHover    = [System.Drawing.Color]::FromArgb(0, 100, 190)
        Success        = [System.Drawing.Color]::FromArgb(16, 124, 16)
        Warning        = [System.Drawing.Color]::FromArgb(157, 93, 0)
        Danger         = [System.Drawing.Color]::FromArgb(196, 43, 28)
        Border         = [System.Drawing.Color]::FromArgb(210, 210, 210)
        InputBack      = [System.Drawing.Color]::FromArgb(255, 255, 255)
        SliderBack     = [System.Drawing.Color]::FromArgb(230, 230, 230)
        StatusBar      = [System.Drawing.Color]::FromArgb(230, 230, 230)
        MenuBack       = [System.Drawing.Color]::FromArgb(249, 249, 249)
    }
    Midnight = @{
        FormBack       = [System.Drawing.Color]::FromArgb(15, 15, 35)
        PanelBack      = [System.Drawing.Color]::FromArgb(22, 22, 48)
        CardBack       = [System.Drawing.Color]::FromArgb(30, 30, 60)
        TextPrimary    = [System.Drawing.Color]::FromArgb(220, 220, 255)
        TextSecondary  = [System.Drawing.Color]::FromArgb(140, 140, 180)
        TextMuted      = [System.Drawing.Color]::FromArgb(80, 80, 120)
        Accent         = [System.Drawing.Color]::FromArgb(100, 100, 255)
        AccentHover    = [System.Drawing.Color]::FromArgb(130, 130, 255)
        Success        = [System.Drawing.Color]::FromArgb(0, 220, 130)
        Warning        = [System.Drawing.Color]::FromArgb(255, 200, 50)
        Danger         = [System.Drawing.Color]::FromArgb(255, 80, 80)
        Border         = [System.Drawing.Color]::FromArgb(50, 50, 90)
        InputBack      = [System.Drawing.Color]::FromArgb(18, 18, 40)
        SliderBack     = [System.Drawing.Color]::FromArgb(40, 40, 75)
        StatusBar      = [System.Drawing.Color]::FromArgb(12, 12, 30)
        MenuBack       = [System.Drawing.Color]::FromArgb(25, 25, 55)
    }
}

$script:CurrentTheme = "Dark"
$script:IsTyping = $false
$script:IsPaused = $false
$script:TypingHistory = [System.Collections.ArrayList]::new()
$script:Profiles = @{}
$script:ConfigPath = Join-Path $env:APPDATA "GhostTyper"
$script:ConfigFile = Join-Path $script:ConfigPath "config.json"
$script:ProfilesFile = Join-Path $script:ConfigPath "profiles.json"
$script:HistoryFile = Join-Path $script:ConfigPath "history.json"

# ═══════════════════════════════════════════════════════════════
# PERSISTENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════
function Initialize-Config {
    if (-not (Test-Path $script:ConfigPath)) {
        New-Item -ItemType Directory -Path $script:ConfigPath -Force | Out-Null
    }
}

function Save-AppConfig {
    Initialize-Config
    $config = @{
        Theme             = $script:CurrentTheme
        Speed             = $speedSlider.Value
        Delay             = $delayNumeric.Value
        HumanizeEnabled   = $humanizeCheck.Checked
        HumanizeVariance  = $varianceSlider.Value
        MistakeRate       = $mistakeSlider.Value
        TopMost           = $script:alwaysOnTopEnabled
        LastText          = $textBox.Text
    }
    $config | ConvertTo-Json -Depth 3 | Set-Content $script:ConfigFile -Encoding UTF8
}

function Load-AppConfig {
    if (Test-Path $script:ConfigFile) {
        try {
            $config = Get-Content $script:ConfigFile -Raw | ConvertFrom-Json
            if ($config.Theme) { $script:CurrentTheme = $config.Theme }
            if ($config.Speed) { $speedSlider.Value = [Math]::Max($speedSlider.Minimum, [Math]::Min($speedSlider.Maximum, [int]$config.Speed)) }
            if ($config.Delay) { $delayNumeric.Value = [Math]::Max(1, [Math]::Min(30, [int]$config.Delay)) }
            if ($null -ne $config.HumanizeEnabled) { $humanizeCheck.Checked = [bool]$config.HumanizeEnabled }
            if ($config.HumanizeVariance) { $varianceSlider.Value = [Math]::Max(0, [Math]::Min(100, [int]$config.HumanizeVariance)) }
            if ($config.MistakeRate) { $mistakeSlider.Value = [Math]::Max(0, [Math]::Min(10, [int]$config.MistakeRate)) }
            if ($null -ne $config.TopMost) { 
                $script:alwaysOnTopEnabled = [bool]$config.TopMost
                $form.TopMost = $script:alwaysOnTopEnabled
                $alwaysOnTopCheck.Checked = $script:alwaysOnTopEnabled
            }
            if ($config.LastText) { $textBox.Text = $config.LastText }
        } catch {}
    }
}

function Save-AppProfiles {
    Initialize-Config
    $script:Profiles | ConvertTo-Json -Depth 3 | Set-Content $script:ProfilesFile -Encoding UTF8
}

function Load-AppProfiles {
    if (Test-Path $script:ProfilesFile) {
        try {
            $loaded = Get-Content $script:ProfilesFile -Raw | ConvertFrom-Json
            $script:Profiles = @{}
            $loaded.PSObject.Properties | ForEach-Object {
                $script:Profiles[$_.Name] = @{
                    Text    = $_.Value.Text
                    Speed   = $_.Value.Speed
                    Delay   = $_.Value.Delay
                }
            }
        } catch {
            $script:Profiles = @{}
        }
    }
}

function Save-AppHistory {
    Initialize-Config
    $historyData = @($script:TypingHistory | Select-Object -Last 50)
    $historyData | ConvertTo-Json -Depth 3 | Set-Content $script:HistoryFile -Encoding UTF8
}

function Load-AppHistory {
    if (Test-Path $script:HistoryFile) {
        try {
            $loaded = Get-Content $script:HistoryFile -Raw | ConvertFrom-Json
            $script:TypingHistory = [System.Collections.ArrayList]@($loaded)
        } catch {
            $script:TypingHistory = [System.Collections.ArrayList]::new()
        }
    }
}

# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════
function Get-Theme {
    return $script:Themes[$script:CurrentTheme]
}

$script:alwaysOnTopEnabled = $false

# ═══════════════════════════════════════════════════════════════
# CREATE MAIN FORM
# ═══════════════════════════════════════════════════════════════
$form = New-Object System.Windows.Forms.Form
$form.Text = "Ghost Typer Pro"
$form.Size = New-Object System.Drawing.Size(680, 720)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "Sizable"
$form.MinimumSize = New-Object System.Drawing.Size(600, 650)
$form.MaximizeBox = $true
$form.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$form.KeyPreview = $true

# Double buffering via reflection
$prop = $form.GetType().GetProperty("DoubleBuffered", [System.Reflection.BindingFlags]"Instance,NonPublic")
$prop.SetValue($form, $true, $null)

# Generate icon
try {
    $iconBitmap = New-Object System.Drawing.Bitmap(32, 32)
    $g = [System.Drawing.Graphics]::FromImage($iconBitmap)
    $g.SmoothingMode = "AntiAlias"
    $g.Clear([System.Drawing.Color]::FromArgb(0, 120, 215))
    $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $g.DrawString("G", (New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)), $brush, 4, 2)
    $brush.Dispose()
    $g.Dispose()
    $form.Icon = [System.Drawing.Icon]::FromHandle($iconBitmap.GetHicon())
} catch {}

# ═══════════════════════════════════════════════════════════════
# MENU STRIP
# ═══════════════════════════════════════════════════════════════
$menuStrip = New-Object System.Windows.Forms.MenuStrip
$menuStrip.RenderMode = "System"

# --- File Menu ---
$fileMenu = New-Object System.Windows.Forms.ToolStripMenuItem("&File")

$importItem = New-Object System.Windows.Forms.ToolStripMenuItem("Import Text from File...")
$importItem.ShortcutKeys = [System.Windows.Forms.Keys]::Control -bor [System.Windows.Forms.Keys]::O
$importItem.Add_Click({
    $ofd = New-Object System.Windows.Forms.OpenFileDialog
    $ofd.Filter = "Text Files|*.txt|All Files|*.*"
    if ($ofd.ShowDialog() -eq "OK") {
        try {
            $textBox.Text = Get-Content $ofd.FileName -Raw -Encoding UTF8
            Update-StatusBar "Imported: $($ofd.FileName)"
        } catch {
            Update-StatusBar "Import failed!"
        }
    }
})
$fileMenu.DropDownItems.Add($importItem) | Out-Null

$exportItem = New-Object System.Windows.Forms.ToolStripMenuItem("Export Text to File...")
$exportItem.ShortcutKeys = [System.Windows.Forms.Keys]::Control -bor [System.Windows.Forms.Keys]::S
$exportItem.Add_Click({
    $sfd = New-Object System.Windows.Forms.SaveFileDialog
    $sfd.Filter = "Text Files|*.txt|All Files|*.*"
    if ($sfd.ShowDialog() -eq "OK") {
        try {
            $textBox.Text | Set-Content $sfd.FileName -Encoding UTF8
            Update-StatusBar "Exported: $($sfd.FileName)"
        } catch {
            Update-StatusBar "Export failed!"
        }
    }
})
$fileMenu.DropDownItems.Add($exportItem) | Out-Null
$fileMenu.DropDownItems.Add((New-Object System.Windows.Forms.ToolStripSeparator)) | Out-Null

$clearItem = New-Object System.Windows.Forms.ToolStripMenuItem("Clear Text")
$clearItem.Add_Click({ $textBox.Clear() })
$fileMenu.DropDownItems.Add($clearItem) | Out-Null
$fileMenu.DropDownItems.Add((New-Object System.Windows.Forms.ToolStripSeparator)) | Out-Null

$exitItem = New-Object System.Windows.Forms.ToolStripMenuItem("E&xit")
$exitItem.Add_Click({ $form.Close() })
$fileMenu.DropDownItems.Add($exitItem) | Out-Null

$menuStrip.Items.Add($fileMenu) | Out-Null

# --- Profiles Menu ---
Add-Type -AssemblyName Microsoft.VisualBasic

$profileMenu = New-Object System.Windows.Forms.ToolStripMenuItem("&Profiles")
$saveProfileItem = New-Object System.Windows.Forms.ToolStripMenuItem("Save Current as Profile...")
$saveProfileItem.Add_Click({
    $nameInput = [Microsoft.VisualBasic.Interaction]::InputBox("Enter profile name:", "Save Profile", "My Profile")
    if (-not [string]::IsNullOrWhiteSpace($nameInput)) {
        $script:Profiles[$nameInput] = @{
            Text  = $textBox.Text
            Speed = $speedSlider.Value
            Delay = $delayNumeric.Value
        }
        Save-AppProfiles
        Update-ProfileMenu
        Update-StatusBar "Profile saved: $nameInput"
    }
})
$profileMenu.DropDownItems.Add($saveProfileItem) | Out-Null
$profileMenu.DropDownItems.Add((New-Object System.Windows.Forms.ToolStripSeparator)) | Out-Null

$script:profileMenuRef = $profileMenu
$menuStrip.Items.Add($profileMenu) | Out-Null

function Update-ProfileMenu {
    while ($script:profileMenuRef.DropDownItems.Count -gt 2) {
        $script:profileMenuRef.DropDownItems.RemoveAt(2)
    }
    
    if ($script:Profiles.Count -eq 0) {
        $noProfiles = New-Object System.Windows.Forms.ToolStripMenuItem("(No saved profiles)")
        $noProfiles.Enabled = $false
        $script:profileMenuRef.DropDownItems.Add($noProfiles) | Out-Null
    } else {
        foreach ($name in ($script:Profiles.Keys | Sort-Object)) {
            $item = New-Object System.Windows.Forms.ToolStripMenuItem("Load: $name")
            $item.Tag = $name
            $item.Add_Click({
                $pName = $this.Tag
                $p = $script:Profiles[$pName]
                if ($p) {
                    $textBox.Text = $p.Text
                    $speedSlider.Value = [Math]::Max($speedSlider.Minimum, [Math]::Min($speedSlider.Maximum, [int]$p.Speed))
                    $delayNumeric.Value = [Math]::Max(1, [Math]::Min(30, [int]$p.Delay))
                    Update-StatusBar "Profile loaded: $pName"
                }
            })
            $script:profileMenuRef.DropDownItems.Add($item) | Out-Null
        }
        $script:profileMenuRef.DropDownItems.Add((New-Object System.Windows.Forms.ToolStripSeparator)) | Out-Null
        $deleteAllItem = New-Object System.Windows.Forms.ToolStripMenuItem("Delete All Profiles")
        $deleteAllItem.Add_Click({
            $result = [System.Windows.Forms.MessageBox]::Show("Delete all saved profiles?", "Confirm", "YesNo", "Warning")
            if ($result -eq "Yes") {
                $script:Profiles = @{}
                Save-AppProfiles
                Update-ProfileMenu
                Update-StatusBar "All profiles deleted"
            }
        })
        $script:profileMenuRef.DropDownItems.Add($deleteAllItem) | Out-Null
    }
}

# --- View Menu ---
$viewMenu = New-Object System.Windows.Forms.ToolStripMenuItem("&View")

$themeSubMenu = New-Object System.Windows.Forms.ToolStripMenuItem("Theme")
foreach ($themeName in @("Dark", "Light", "Midnight")) {
    $themeItem = New-Object System.Windows.Forms.ToolStripMenuItem($themeName)
    $themeItem.Tag = $themeName
    $themeItem.Add_Click({
        $script:CurrentTheme = $this.Tag
        Apply-Theme
        Update-StatusBar "Theme: $($this.Tag)"
    })
    $themeSubMenu.DropDownItems.Add($themeItem) | Out-Null
}
$viewMenu.DropDownItems.Add($themeSubMenu) | Out-Null

$alwaysOnTopCheck = New-Object System.Windows.Forms.ToolStripMenuItem("Always On Top")
$alwaysOnTopCheck.CheckOnClick = $true
$alwaysOnTopCheck.Add_CheckedChanged({
    $script:alwaysOnTopEnabled = $alwaysOnTopCheck.Checked
    $form.TopMost = $script:alwaysOnTopEnabled
})
$viewMenu.DropDownItems.Add($alwaysOnTopCheck) | Out-Null
$viewMenu.DropDownItems.Add((New-Object System.Windows.Forms.ToolStripSeparator)) | Out-Null

$historyItem = New-Object System.Windows.Forms.ToolStripMenuItem("Typing History...")
$historyItem.ShortcutKeys = [System.Windows.Forms.Keys]::Control -bor [System.Windows.Forms.Keys]::H
$historyItem.Add_Click({ Show-HistoryDialog })
$viewMenu.DropDownItems.Add($historyItem) | Out-Null

$menuStrip.Items.Add($viewMenu) | Out-Null

# --- Help Menu ---
$helpMenu = New-Object System.Windows.Forms.ToolStripMenuItem("&Help")

$shortcutsItem = New-Object System.Windows.Forms.ToolStripMenuItem("Keyboard Shortcuts...")
$shortcutsItem.ShortcutKeys = [System.Windows.Forms.Keys]::F1
$shortcutsItem.Add_Click({
    $shortcuts = @"
KEYBOARD SHORTCUTS
===================================
Ctrl+O          Import text file
Ctrl+S          Export text file
Ctrl+H          Typing history
Ctrl+Enter      Start typing
F1              Show this help

DURING TYPING:
===================================
ESC             Stop typing
Pause/Break     Pause / Resume
"@
    [System.Windows.Forms.MessageBox]::Show($shortcuts, "Keyboard Shortcuts", "OK", "Information")
})
$helpMenu.DropDownItems.Add($shortcutsItem) | Out-Null

$aboutItem = New-Object System.Windows.Forms.ToolStripMenuItem("About Ghost Typer Pro")
$aboutItem.Add_Click({
    [System.Windows.Forms.MessageBox]::Show(
        "Ghost Typer Pro v2.0`n`nAdvanced auto-typing tool with:`n- Human-like typing simulation`n- Mistake emulation`n- Profile management`n- Global hotkey support`n- Typing history`n- Multi-theme UI",
        "About", "OK", "Information"
    )
})
$helpMenu.DropDownItems.Add($aboutItem) | Out-Null

$menuStrip.Items.Add($helpMenu) | Out-Null

$form.MainMenuStrip = $menuStrip
$form.Controls.Add($menuStrip)

# ═══════════════════════════════════════════════════════════════
# MAIN LAYOUT
# ═══════════════════════════════════════════════════════════════
$mainPanel = New-Object System.Windows.Forms.Panel
$mainPanel.Dock = "Fill"
$mainPanel.Padding = New-Object System.Windows.Forms.Padding(15, 5, 15, 5)
$form.Controls.Add($mainPanel)
$mainPanel.BringToFront()

# --- Header ---
$headerPanel = New-Object System.Windows.Forms.Panel
$headerPanel.Dock = "Top"
$headerPanel.Height = 50
$mainPanel.Controls.Add($headerPanel)

$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = "GHOST TYPER PRO"
$titleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
$titleLabel.Dock = "Left"
$titleLabel.AutoSize = $true
$titleLabel.Padding = New-Object System.Windows.Forms.Padding(0, 8, 0, 0)
$headerPanel.Controls.Add($titleLabel)

$subtitleLabel = New-Object System.Windows.Forms.Label
$subtitleLabel.Text = "Advanced Auto-Typing Tool"
$subtitleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$subtitleLabel.Dock = "Right"
$subtitleLabel.AutoSize = $true
$subtitleLabel.Padding = New-Object System.Windows.Forms.Padding(0, 16, 10, 0)
$headerPanel.Controls.Add($subtitleLabel)

# ═══════════════════════════════════════════════════════════════
# TEXT INPUT SECTION
# ═══════════════════════════════════════════════════════════════
$textGroupBox = New-Object System.Windows.Forms.GroupBox
$textGroupBox.Text = "  Text to Type  "
$textGroupBox.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$textGroupBox.Dock = "Top"
$textGroupBox.Height = 230
$textGroupBox.Padding = New-Object System.Windows.Forms.Padding(10, 5, 10, 10)
$mainPanel.Controls.Add($textGroupBox)
$textGroupBox.BringToFront()

$textBox = New-Object System.Windows.Forms.RichTextBox
$textBox.Dock = "Fill"
$textBox.Font = New-Object System.Drawing.Font("Consolas", 10)
$textBox.BorderStyle = "None"
$textBox.AcceptsTab = $true
$textBox.DetectUrls = $false
$textGroupBox.Controls.Add($textBox)

# Stats panel
$statsPanel = New-Object System.Windows.Forms.Panel
$statsPanel.Dock = "Bottom"
$statsPanel.Height = 22
$textGroupBox.Controls.Add($statsPanel)

$charCountLabel = New-Object System.Windows.Forms.Label
$charCountLabel.Text = "0 characters | 0 words | 0 lines"
$charCountLabel.Font = New-Object System.Drawing.Font("Segoe UI", 8)
$charCountLabel.Dock = "Left"
$charCountLabel.AutoSize = $true
$charCountLabel.Padding = New-Object System.Windows.Forms.Padding(0, 4, 0, 0)
$statsPanel.Controls.Add($charCountLabel)

$etaLabel = New-Object System.Windows.Forms.Label
$etaLabel.Text = "ETA: 0s"
$etaLabel.Font = New-Object System.Drawing.Font("Segoe UI", 8)
$etaLabel.Dock = "Right"
$etaLabel.AutoSize = $true
$etaLabel.Padding = New-Object System.Windows.Forms.Padding(0, 4, 5, 0)
$statsPanel.Controls.Add($etaLabel)

function Update-TextStats {
    $text = $textBox.Text
    $chars = $text.Length
    $words = if ($chars -gt 0) { @($text -split '\s+' | Where-Object { $_ }).Count } else { 0 }
    $lines = if ($chars -gt 0) { ($text -split "`n").Count } else { 0 }
    $charCountLabel.Text = "$chars characters | $words words | $lines lines"
    
    $totalMs = $chars * $speedSlider.Value
    $totalSec = [Math]::Ceiling($totalMs / 1000)
    if ($totalSec -lt 60) {
        $etaLabel.Text = "ETA: ${totalSec}s"
    } elseif ($totalSec -lt 3600) {
        $min = [Math]::Floor($totalSec / 60)
        $sec = $totalSec % 60
        $etaLabel.Text = "ETA: ${min}m ${sec}s"
    } else {
        $hr = [Math]::Floor($totalSec / 3600)
        $min = [Math]::Floor(($totalSec % 3600) / 60)
        $etaLabel.Text = "ETA: ${hr}h ${min}m"
    }
}

$textBox.Add_TextChanged({ Update-TextStats })

# ═══════════════════════════════════════════════════════════════
# SETTINGS TABS
# ═══════════════════════════════════════════════════════════════
$settingsTabControl = New-Object System.Windows.Forms.TabControl
$settingsTabControl.Dock = "Top"
$settingsTabControl.Height = 200
$settingsTabControl.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$mainPanel.Controls.Add($settingsTabControl)
$settingsTabControl.BringToFront()

# ─── Tab 1: Speed & Timing ───
$speedTab = New-Object System.Windows.Forms.TabPage
$speedTab.Text = "Speed & Timing"
$speedTab.Padding = New-Object System.Windows.Forms.Padding(15, 10, 15, 10)
$settingsTabControl.TabPages.Add($speedTab)

$speedPanel = New-Object System.Windows.Forms.Panel
$speedPanel.Dock = "Top"
$speedPanel.Height = 70

$speedTitleLabel = New-Object System.Windows.Forms.Label
$speedTitleLabel.Text = "Typing Speed"
$speedTitleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$speedTitleLabel.Location = New-Object System.Drawing.Point(0, 0)
$speedTitleLabel.AutoSize = $true
$speedPanel.Controls.Add($speedTitleLabel)

$speedValueLabel = New-Object System.Windows.Forms.Label
$speedValueLabel.Text = "50 ms/char (~240 WPM)"
$speedValueLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$speedValueLabel.Location = New-Object System.Drawing.Point(0, 18)
$speedValueLabel.AutoSize = $true
$speedPanel.Controls.Add($speedValueLabel)

$speedSlider = New-Object System.Windows.Forms.TrackBar
$speedSlider.Minimum = 5
$speedSlider.Maximum = 300
$speedSlider.Value = 50
$speedSlider.TickFrequency = 25
$speedSlider.LargeChange = 25
$speedSlider.SmallChange = 5
$speedSlider.Location = New-Object System.Drawing.Point(0, 38)
$speedSlider.Size = New-Object System.Drawing.Size(580, 30)
$speedPanel.Controls.Add($speedSlider)

$speedMinLabel = New-Object System.Windows.Forms.Label
$speedMinLabel.Text = "Blazing (5ms)"
$speedMinLabel.Font = New-Object System.Drawing.Font("Segoe UI", 7)
$speedMinLabel.Location = New-Object System.Drawing.Point(0, 55)
$speedMinLabel.AutoSize = $true
$speedPanel.Controls.Add($speedMinLabel)

$speedMaxLabel = New-Object System.Windows.Forms.Label
$speedMaxLabel.Text = "Slow (300ms)"
$speedMaxLabel.Font = New-Object System.Drawing.Font("Segoe UI", 7)
$speedMaxLabel.Location = New-Object System.Drawing.Point(520, 55)
$speedMaxLabel.AutoSize = $true
$speedPanel.Controls.Add($speedMaxLabel)

$speedTab.Controls.Add($speedPanel)

function Update-SpeedDisplay {
    $ms = $speedSlider.Value
    $wpm = [Math]::Round(12000 / $ms)
    $speedValueLabel.Text = "$ms ms/char (~$wpm WPM)"
    Update-TextStats
}

$speedSlider.Add_ValueChanged({ Update-SpeedDisplay })

# Delay control
$delayPanel = New-Object System.Windows.Forms.Panel
$delayPanel.Dock = "Top"
$delayPanel.Height = 50

$delayLabel = New-Object System.Windows.Forms.Label
$delayLabel.Text = "Start Delay (seconds):"
$delayLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$delayLabel.Location = New-Object System.Drawing.Point(0, 10)
$delayLabel.AutoSize = $true
$delayPanel.Controls.Add($delayLabel)

$delayNumeric = New-Object System.Windows.Forms.NumericUpDown
$delayNumeric.Minimum = 1
$delayNumeric.Maximum = 30
$delayNumeric.Value = 3
$delayNumeric.Location = New-Object System.Drawing.Point(180, 7)
$delayNumeric.Size = New-Object System.Drawing.Size(60, 25)
$delayNumeric.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$delayPanel.Controls.Add($delayNumeric)

$delayHintLabel = New-Object System.Windows.Forms.Label
$delayHintLabel.Text = "Time to switch to target window"
$delayHintLabel.Font = New-Object System.Drawing.Font("Segoe UI", 8)
$delayHintLabel.Location = New-Object System.Drawing.Point(250, 12)
$delayHintLabel.AutoSize = $true
$delayPanel.Controls.Add($delayHintLabel)

$speedTab.Controls.Add($delayPanel)
$delayPanel.BringToFront()

# Speed presets
$presetPanel = New-Object System.Windows.Forms.Panel
$presetPanel.Dock = "Top"
$presetPanel.Height = 40

$presetLabel = New-Object System.Windows.Forms.Label
$presetLabel.Text = "Presets:"
$presetLabel.Font = New-Object System.Drawing.Font("Segoe UI", 8, [System.Drawing.FontStyle]::Bold)
$presetLabel.Location = New-Object System.Drawing.Point(0, 10)
$presetLabel.AutoSize = $true
$presetPanel.Controls.Add($presetLabel)

$presets = @(
    @{Name="Instant"; Value=5},
    @{Name="Fast"; Value=20},
    @{Name="Normal"; Value=50},
    @{Name="Human"; Value=85},
    @{Name="Slow"; Value=150},
    @{Name="Hunt&Peck"; Value=250}
)

$xPos = 55
foreach ($preset in $presets) {
    $btn = New-Object System.Windows.Forms.Button
    $btn.Text = $preset.Name
    $btn.Size = New-Object System.Drawing.Size(80, 26)
    $btn.Location = New-Object System.Drawing.Point($xPos, 5)
    $btn.FlatStyle = "Flat"
    $btn.Font = New-Object System.Drawing.Font("Segoe UI", 7.5)
    $btn.Tag = $preset.Value
    $btn.Cursor = [System.Windows.Forms.Cursors]::Hand
    $btn.Add_Click({ $speedSlider.Value = [int]$this.Tag })
    $presetPanel.Controls.Add($btn)
    $xPos += 88
}

$speedTab.Controls.Add($presetPanel)
$presetPanel.BringToFront()

# ─── Tab 2: Human Simulation ───
$humanTab = New-Object System.Windows.Forms.TabPage
$humanTab.Text = "Human Simulation"
$humanTab.Padding = New-Object System.Windows.Forms.Padding(15, 10, 15, 10)
$settingsTabControl.TabPages.Add($humanTab)

$humanizeCheck = New-Object System.Windows.Forms.CheckBox
$humanizeCheck.Text = "Enable human-like typing variation"
$humanizeCheck.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$humanizeCheck.Location = New-Object System.Drawing.Point(0, 5)
$humanizeCheck.AutoSize = $true
$humanizeCheck.Checked = $true
$humanTab.Controls.Add($humanizeCheck)

$humanDescLabel = New-Object System.Windows.Forms.Label
$humanDescLabel.Text = "Adds random speed variation to simulate natural typing rhythm."
$humanDescLabel.Font = New-Object System.Drawing.Font("Segoe UI", 8)
$humanDescLabel.Location = New-Object System.Drawing.Point(20, 28)
$humanDescLabel.AutoSize = $true
$humanTab.Controls.Add($humanDescLabel)

$varianceLabel = New-Object System.Windows.Forms.Label
$varianceLabel.Text = "Speed Variance:"
$varianceLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$varianceLabel.Location = New-Object System.Drawing.Point(0, 55)
$varianceLabel.AutoSize = $true
$humanTab.Controls.Add($varianceLabel)

$varianceValueLabel = New-Object System.Windows.Forms.Label
$varianceValueLabel.Text = "+/- 30%"
$varianceValueLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$varianceValueLabel.Location = New-Object System.Drawing.Point(120, 55)
$varianceValueLabel.AutoSize = $true
$humanTab.Controls.Add($varianceValueLabel)

$varianceSlider = New-Object System.Windows.Forms.TrackBar
$varianceSlider.Minimum = 0
$varianceSlider.Maximum = 100
$varianceSlider.Value = 30
$varianceSlider.TickFrequency = 10
$varianceSlider.Location = New-Object System.Drawing.Point(0, 75)
$varianceSlider.Size = New-Object System.Drawing.Size(580, 30)
$humanTab.Controls.Add($varianceSlider)

$varianceSlider.Add_ValueChanged({
    $varianceValueLabel.Text = "+/- $($varianceSlider.Value)%"
})

$mistakeLabel = New-Object System.Windows.Forms.Label
$mistakeLabel.Text = "Typo Simulation Rate:"
$mistakeLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$mistakeLabel.Location = New-Object System.Drawing.Point(0, 105)
$mistakeLabel.AutoSize = $true
$humanTab.Controls.Add($mistakeLabel)

$mistakeValueLabel = New-Object System.Windows.Forms.Label
$mistakeValueLabel.Text = "0% (disabled)"
$mistakeValueLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$mistakeValueLabel.Location = New-Object System.Drawing.Point(160, 105)
$mistakeValueLabel.AutoSize = $true
$humanTab.Controls.Add($mistakeValueLabel)

$mistakeSlider = New-Object System.Windows.Forms.TrackBar
$mistakeSlider.Minimum = 0
$mistakeSlider.Maximum = 10
$mistakeSlider.Value = 0
$mistakeSlider.TickFrequency = 1
$mistakeSlider.Location = New-Object System.Drawing.Point(0, 125)
$mistakeSlider.Size = New-Object System.Drawing.Size(580, 30)
$humanTab.Controls.Add($mistakeSlider)

$mistakeDescLabel = New-Object System.Windows.Forms.Label
$mistakeDescLabel.Text = "Types a wrong key then backspaces to correct it - simulates real typos."
$mistakeDescLabel.Font = New-Object System.Drawing.Font("Segoe UI", 8)
$mistakeDescLabel.Location = New-Object System.Drawing.Point(20, 148)
$mistakeDescLabel.AutoSize = $true
$humanTab.Controls.Add($mistakeDescLabel)

$mistakeSlider.Add_ValueChanged({
    $val = $mistakeSlider.Value
    if ($val -eq 0) { $mistakeValueLabel.Text = "0% (disabled)" }
    else { $mistakeValueLabel.Text = "$val%" }
})

# ═══════════════════════════════════════════════════════════════
# PROGRESS BAR
# ═══════════════════════════════════════════════════════════════
$progressPanel = New-Object System.Windows.Forms.Panel
$progressPanel.Dock = "Top"
$progressPanel.Height = 35
$mainPanel.Controls.Add($progressPanel)
$progressPanel.BringToFront()

$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Dock = "Fill"
$progressBar.Style = "Continuous"
$progressPanel.Controls.Add($progressBar)

$progressLabel = New-Object System.Windows.Forms.Label
$progressLabel.Text = "Ready"
$progressLabel.Dock = "Bottom"
$progressLabel.Font = New-Object System.Drawing.Font("Segoe UI", 8)
$progressLabel.TextAlign = "MiddleCenter"
$progressLabel.Height = 15
$progressPanel.Controls.Add($progressLabel)

# ═══════════════════════════════════════════════════════════════
# ACTION BUTTONS
# ═══════════════════════════════════════════════════════════════
$buttonPanel = New-Object System.Windows.Forms.Panel
$buttonPanel.Dock = "Top"
$buttonPanel.Height = 55
$mainPanel.Controls.Add($buttonPanel)
$buttonPanel.BringToFront()

$startButton = New-Object System.Windows.Forms.Button
$startButton.Text = "START TYPING"
$startButton.Size = New-Object System.Drawing.Size(300, 45)
$startButton.Location = New-Object System.Drawing.Point(0, 5)
$startButton.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$startButton.FlatStyle = "Flat"
$startButton.Cursor = [System.Windows.Forms.Cursors]::Hand
$buttonPanel.Controls.Add($startButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = "STOP"
$stopButton.Size = New-Object System.Drawing.Size(120, 45)
$stopButton.Location = New-Object System.Drawing.Point(310, 5)
$stopButton.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$stopButton.FlatStyle = "Flat"
$stopButton.Cursor = [System.Windows.Forms.Cursors]::Hand
$stopButton.Enabled = $false
$buttonPanel.Controls.Add($stopButton)

$pauseButton = New-Object System.Windows.Forms.Button
$pauseButton.Text = "PAUSE"
$pauseButton.Size = New-Object System.Drawing.Size(80, 45)
$pauseButton.Location = New-Object System.Drawing.Point(440, 5)
$pauseButton.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$pauseButton.FlatStyle = "Flat"
$pauseButton.Cursor = [System.Windows.Forms.Cursors]::Hand
$pauseButton.Enabled = $false
$buttonPanel.Controls.Add($pauseButton)

# ═══════════════════════════════════════════════════════════════
# STATUS BAR
# ═══════════════════════════════════════════════════════════════
$statusBar = New-Object System.Windows.Forms.StatusStrip
$statusBarLabel = New-Object System.Windows.Forms.ToolStripStatusLabel
$statusBarLabel.Text = "Ready - Press Ctrl+Enter or click Start"
$statusBarLabel.Spring = $true
$statusBarLabel.TextAlign = "MiddleLeft"
$statusBar.Items.Add($statusBarLabel) | Out-Null

$statusBarRight = New-Object System.Windows.Forms.ToolStripStatusLabel
$statusBarRight.Text = "v2.0"
$statusBarRight.Alignment = "Right"
$statusBar.Items.Add($statusBarRight) | Out-Null

$form.Controls.Add($statusBar)

function Update-StatusBar {
    param([string]$Message)
    $statusBarLabel.Text = $Message
}

# ═══════════════════════════════════════════════════════════════
# COUNTDOWN OVERLAY
# ═══════════════════════════════════════════════════════════════
function Show-Countdown {
    param([int]$Seconds)
    
    $countdownForm = New-Object System.Windows.Forms.Form
    $countdownForm.FormBorderStyle = "None"
    $countdownForm.Size = New-Object System.Drawing.Size(200, 200)
    $countdownForm.StartPosition = "CenterScreen"
    $countdownForm.TopMost = $true
    $countdownForm.BackColor = [System.Drawing.Color]::FromArgb(20, 20, 20)
    $countdownForm.Opacity = 0.9
    $countdownForm.ShowInTaskbar = $false
    
    try {
        $path = New-Object System.Drawing.Drawing2D.GraphicsPath
        $path.AddEllipse(0, 0, 200, 200)
        $countdownForm.Region = New-Object System.Drawing.Region($path)
    } catch {}
    
    $countdownLabel = New-Object System.Windows.Forms.Label
    $countdownLabel.Dock = "Fill"
    $countdownLabel.Font = New-Object System.Drawing.Font("Segoe UI", 48, [System.Drawing.FontStyle]::Bold)
    $countdownLabel.ForeColor = [System.Drawing.Color]::White
    $countdownLabel.TextAlign = "MiddleCenter"
    $countdownForm.Controls.Add($countdownLabel)
    
    $countdownForm.Show()
    
    for ($i = $Seconds; $i -ge 1; $i--) {
        $countdownLabel.Text = $i.ToString()
        $countdownForm.Refresh()
        [System.Windows.Forms.Application]::DoEvents()
        Start-Sleep -Seconds 1
    }
    
    $countdownLabel.Text = "GO!"
    $countdownLabel.ForeColor = [System.Drawing.Color]::FromArgb(0, 255, 100)
    $countdownForm.Refresh()
    Start-Sleep -Milliseconds 300
    
    $countdownForm.Close()
    $countdownForm.Dispose()
}

# ═══════════════════════════════════════════════════════════════
# HISTORY DIALOG
# ═══════════════════════════════════════════════════════════════
function Show-HistoryDialog {
    $histForm = New-Object System.Windows.Forms.Form
    $histForm.Text = "Typing History"
    $histForm.Size = New-Object System.Drawing.Size(650, 400)
    $histForm.StartPosition = "CenterParent"
    $histForm.MinimumSize = New-Object System.Drawing.Size(400, 300)
    
    $t = Get-Theme
    $histForm.BackColor = $t.FormBack
    $histForm.ForeColor = $t.TextPrimary
    
    $listView = New-Object System.Windows.Forms.ListView
    $listView.Dock = "Fill"
    $listView.View = "Details"
    $listView.FullRowSelect = $true
    $listView.GridLines = $true
    $listView.BackColor = $t.CardBack
    $listView.ForeColor = $t.TextPrimary
    $listView.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    
    $listView.Columns.Add("Date", 140) | Out-Null
    $listView.Columns.Add("Characters", 80) | Out-Null
    $listView.Columns.Add("Speed (ms)", 80) | Out-Null
    $listView.Columns.Add("Duration", 80) | Out-Null
    $listView.Columns.Add("Status", 80) | Out-Null
    $listView.Columns.Add("Preview", 180) | Out-Null
    
    foreach ($entry in @($script:TypingHistory | Sort-Object { $_.Date } -Descending)) {
        $item = New-Object System.Windows.Forms.ListViewItem($entry.Date.ToString())
        $item.SubItems.Add($entry.Characters.ToString()) | Out-Null
        $item.SubItems.Add($entry.Speed.ToString()) | Out-Null
        $item.SubItems.Add($entry.Duration.ToString()) | Out-Null
        $item.SubItems.Add($entry.Status.ToString()) | Out-Null
        $preview = $entry.Preview.ToString()
        if ($preview.Length -gt 40) { $preview = $preview.Substring(0, 40) + "..." }
        $item.SubItems.Add($preview) | Out-Null
        $listView.Items.Add($item) | Out-Null
    }
    
    $histForm.Controls.Add($listView)
    
    $clearHistBtn = New-Object System.Windows.Forms.Button
    $clearHistBtn.Text = "Clear History"
    $clearHistBtn.Dock = "Bottom"
    $clearHistBtn.Height = 35
    $clearHistBtn.FlatStyle = "Flat"
    $clearHistBtn.BackColor = $t.Danger
    $clearHistBtn.ForeColor = [System.Drawing.Color]::White
    $clearHistBtn.Add_Click({
        $script:TypingHistory.Clear()
        Save-AppHistory
        $histForm.Close()
    })
    $histForm.Controls.Add($clearHistBtn)
    
    $histForm.ShowDialog()
}

# ═══════════════════════════════════════════════════════════════
# THEME APPLICATION
# ═══════════════════════════════════════════════════════════════
function Apply-Theme {
    $t = Get-Theme
    
    $form.BackColor = $t.FormBack
    $form.ForeColor = $t.TextPrimary
    
    # Menu
    $menuStrip.BackColor = $t.MenuBack
    $menuStrip.ForeColor = $t.TextPrimary
    foreach ($item in $menuStrip.Items) {
        $item.ForeColor = $t.TextPrimary
        $item.BackColor = $t.MenuBack
        if ($item.HasDropDownItems) {
            foreach ($sub in $item.DropDownItems) {
                if ($sub -is [System.Windows.Forms.ToolStripMenuItem]) {
                    $sub.ForeColor = $t.TextPrimary
                    $sub.BackColor = $t.MenuBack
                }
            }
        }
    }
    
    $mainPanel.BackColor = $t.FormBack
    $headerPanel.BackColor = $t.FormBack
    $titleLabel.ForeColor = $t.Accent
    $subtitleLabel.ForeColor = $t.TextMuted
    
    $textGroupBox.ForeColor = $t.TextPrimary
    $textGroupBox.BackColor = $t.CardBack
    $textBox.BackColor = $t.InputBack
    $textBox.ForeColor = $t.TextPrimary
    
    $statsPanel.BackColor = $t.CardBack
    $charCountLabel.ForeColor = $t.TextMuted
    $etaLabel.ForeColor = $t.Accent
    
    # Tabs
    $settingsTabControl.BackColor = $t.CardBack
    foreach ($tab in $settingsTabControl.TabPages) {
        $tab.BackColor = $t.CardBack
        $tab.ForeColor = $t.TextPrimary
        foreach ($ctrl in $tab.Controls) {
            if ($ctrl -is [System.Windows.Forms.Label]) { $ctrl.ForeColor = $t.TextPrimary }
            if ($ctrl -is [System.Windows.Forms.CheckBox]) { $ctrl.ForeColor = $t.TextPrimary }
            if ($ctrl -is [System.Windows.Forms.Panel]) {
                $ctrl.BackColor = $t.CardBack
                foreach ($child in $ctrl.Controls) {
                    if ($child -is [System.Windows.Forms.Label]) { $child.ForeColor = $t.TextPrimary }
                    if ($child -is [System.Windows.Forms.Button]) {
                        $child.BackColor = $t.SliderBack
                        $child.ForeColor = $t.TextPrimary
                        $child.FlatAppearance.BorderColor = $t.Border
                    }
                }
            }
            if ($ctrl -is [System.Windows.Forms.TrackBar]) { $ctrl.BackColor = $t.CardBack }
            if ($ctrl -is [System.Windows.Forms.NumericUpDown]) {
                $ctrl.BackColor = $t.InputBack
                $ctrl.ForeColor = $t.TextPrimary
            }
        }
    }
    
    $humanDescLabel.ForeColor = $t.TextMuted
    $mistakeDescLabel.ForeColor = $t.TextMuted
    $speedMinLabel.ForeColor = $t.TextMuted
    $speedMaxLabel.ForeColor = $t.TextMuted
    $delayHintLabel.ForeColor = $t.TextMuted
    $varianceValueLabel.ForeColor = $t.Accent
    
    $progressPanel.BackColor = $t.FormBack
    $progressLabel.ForeColor = $t.TextSecondary
    $progressLabel.BackColor = $t.FormBack
    
    $startButton.BackColor = $t.Success
    $startButton.ForeColor = [System.Drawing.Color]::White
    $startButton.FlatAppearance.BorderSize = 0
    
    $stopButton.BackColor = $t.Danger
    $stopButton.ForeColor = [System.Drawing.Color]::White
    $stopButton.FlatAppearance.BorderSize = 0
    
    $pauseButton.BackColor = $t.Warning
    $pauseButton.ForeColor = [System.Drawing.Color]::FromArgb(30, 30, 30)
    $pauseButton.FlatAppearance.BorderSize = 0
    
    $buttonPanel.BackColor = $t.FormBack
    
    $statusBar.BackColor = $t.StatusBar
    $statusBarLabel.ForeColor = $t.TextSecondary
    $statusBarRight.ForeColor = $t.TextMuted
}

# ═══════════════════════════════════════════════════════════════
# TYPING ENGINE HELPERS
# ═══════════════════════════════════════════════════════════════
function Get-HumanizedDelay {
    param([int]$BaseDelay, [char]$CurrentChar, [char]$PrevChar)
    
    if (-not $humanizeCheck.Checked) { return $BaseDelay }
    
    $variance = $varianceSlider.Value / 100.0
    $minMult = [Math]::Max(0.1, (1.0 - $variance))
    $maxMult = 1.0 + $variance
    $random = Get-Random -Minimum ($minMult * 1000) -Maximum ($maxMult * 1000)
    $random = $random / 1000.0
    $delay = [int]($BaseDelay * $random)
    
    # Pause after punctuation
    if ("$CurrentChar" -match '[.!?]') {
        $delay += Get-Random -Minimum ($BaseDelay * 2) -Maximum ($BaseDelay * 5)
    }
    
    # Slight delay at word start
    if ($PrevChar -eq ' ') {
        $delay += Get-Random -Minimum 0 -Maximum $BaseDelay
    }
    
    # Speed up for vowels after consonants
    if ("$CurrentChar" -match '[aeiou]' -and "$PrevChar" -match '[a-z]') {
        $delay = [int]($delay * 0.85)
    }
    
    return [Math]::Max(2, $delay)
}

function Get-NearbyKey {
    param([char]$Key)
    $keyMap = @{
        'a' = 's','q','w','z'
        'b' = 'v','n','g','h'
        'c' = 'x','v','d','f'
        'd' = 's','f','e','r'
        'e' = 'w','r','d','s'
        'f' = 'd','g','r','t'
        'g' = 'f','h','t','y'
        'h' = 'g','j','y','u'
        'i' = 'u','o','k','j'
        'j' = 'h','k','u','i'
        'k' = 'j','l','i','o'
        'l' = 'k','o','p'
        'm' = 'n','j','k'
        'n' = 'b','m','h','j'
        'o' = 'i','p','l','k'
        'p' = 'o','l'
        'q' = 'w','a'
        'r' = 'e','t','d','f'
        's' = 'a','d','w','e'
        't' = 'r','y','f','g'
        'u' = 'y','i','h','j'
        'v' = 'c','b','f','g'
        'w' = 'q','e','a','s'
        'x' = 'z','c','s','d'
        'y' = 't','u','g','h'
        'z' = 'a','x','s'
    }
    
    $lower = "$([char]::ToLower($Key))"
    if ($keyMap.ContainsKey($lower)) {
        $nearby = $keyMap[$lower]
        $wrongKey = $nearby | Get-Random
        if ([char]::IsUpper($Key)) { return [char]::ToUpper([char]$wrongKey) }
        return $wrongKey
    }
    return "$Key"
}

function Get-EscapedSendKey {
    param([char]$Char)
    switch ($Char) {
        '+' { return '{+}' }
        '^' { return '{^}' }
        '%' { return '{%}' }
        '~' { return '{~}' }
        '(' { return '{(}' }
        ')' { return '{)}' }
        '[' { return '{[}' }
        ']' { return '{]}' }
        '{' { return '{{}' }
        '}' { return '{}}' }
        default { return "$Char" }
    }
}

# ═══════════════════════════════════════════════════════════════
# BUTTON EVENTS
# ═══════════════════════════════════════════════════════════════
$stopButton.Add_Click({
    [GlobalKeyboardHook]::EscapePressed = $true
})

$pauseButton.Add_Click({
    $script:IsPaused = -not $script:IsPaused
    if ($script:IsPaused) {
        $pauseButton.Text = "RESUME"
        Update-StatusBar "PAUSED - Click Resume or press Pause/Break key"
    } else {
        $pauseButton.Text = "PAUSE"
        Update-StatusBar "Resumed typing..."
    }
})

# ═══════════════════════════════════════════════════════════════
# MAIN TYPING LOGIC
# ═══════════════════════════════════════════════════════════════
$startButton.Add_Click({
    $text = $textBox.Text
    
    if ([string]::IsNullOrWhiteSpace($text)) {
        [System.Windows.Forms.MessageBox]::Show(
            "Please enter some text to type.",
            "No Text",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Warning
        )
        return
    }
    
    $delay = $speedSlider.Value
    $startDelay = [int]$delayNumeric.Value
    $mistakeRate = $mistakeSlider.Value / 100.0
    
    [GlobalKeyboardHook]::Reset()
    $script:IsTyping = $true
    $script:IsPaused = $false
    
    # UI: typing mode
    $startButton.Enabled = $false
    $stopButton.Enabled = $true
    $pauseButton.Enabled = $true
    $pauseButton.Text = "PAUSE"
    $textBox.ReadOnly = $true
    $settingsTabControl.Enabled = $false
    
    $progressBar.Minimum = 0
    $progressBar.Maximum = $text.Length
    $progressBar.Value = 0
    
    [GlobalKeyboardHook]::Install()
    
    $form.WindowState = "Minimized"
    Start-Sleep -Milliseconds 300
    
    Show-Countdown -Seconds $startDelay
    
    # Typing loop
    $typedChars = 0
    $mistakes = 0
    $startTime = Get-Date
    $prevChar = [char]' '
    $chars = $text.ToCharArray()
    
    for ($i = 0; $i -lt $chars.Length; $i++) {
        # Check stop
        if ([GlobalKeyboardHook]::EscapePressed) {
            $script:IsTyping = $false
            break
        }
        
        # Check pause
        while ($script:IsPaused -and -not [GlobalKeyboardHook]::EscapePressed) {
            [System.Windows.Forms.Application]::DoEvents()
            Start-Sleep -Milliseconds 50
            if ([GlobalKeyboardHook]::PausePressed) {
                [GlobalKeyboardHook]::PausePressed = $false
                $script:IsPaused = $false
                $pauseButton.Text = "PAUSE"
            }
        }
        
        if ([GlobalKeyboardHook]::EscapePressed) {
            $script:IsTyping = $false
            break
        }
        
        # Pause/Break toggle
        if ([GlobalKeyboardHook]::PausePressed) {
            [GlobalKeyboardHook]::PausePressed = $false
            $script:IsPaused = $true
            $pauseButton.Text = "RESUME"
            Update-StatusBar "PAUSED at char $typedChars / $($text.Length)"
            continue
        }
        
        $char = $chars[$i]
        
        # Mistake simulation
        if ($mistakeRate -gt 0 -and "$char" -match '[a-zA-Z]') {
            $roll = (Get-Random -Minimum 0 -Maximum 1000) / 1000.0
            if ($roll -lt $mistakeRate) {
                $wrongKey = Get-NearbyKey -Key $char
                $wrongEscaped = Get-EscapedSendKey -Char ([char]$wrongKey)
                try {
                    [System.Windows.Forms.SendKeys]::SendWait($wrongEscaped)
                    $mistakes++
                    Start-Sleep -Milliseconds (Get-Random -Minimum 100 -Maximum 300)
                    [System.Windows.Forms.SendKeys]::SendWait("{BACKSPACE}")
                    Start-Sleep -Milliseconds (Get-Random -Minimum 50 -Maximum 150)
                } catch {}
            }
        }
        
        # Send the actual character
        if ($char -eq "`n") {
            try { [System.Windows.Forms.SendKeys]::SendWait("{ENTER}") } catch {}
        }
        elseif ($char -eq "`r") {
            # Skip carriage return
        }
        elseif ($char -eq "`t") {
            try { [System.Windows.Forms.SendKeys]::SendWait("{TAB}") } catch {}
        }
        else {
            $escaped = Get-EscapedSendKey -Char $char
            try { [System.Windows.Forms.SendKeys]::SendWait($escaped) } catch {}
        }
        
        $typedChars++
        
        # Humanized delay
        $actualDelay = Get-HumanizedDelay -BaseDelay $delay -CurrentChar $char -PrevChar $prevChar
        Start-Sleep -Milliseconds $actualDelay
        
        $prevChar = $char
        
        # Update progress every 10 chars
        if ($typedChars % 10 -eq 0 -or $typedChars -eq $text.Length) {
            $progressBar.Value = [Math]::Min($typedChars, $progressBar.Maximum)
            $pct = [Math]::Round(($typedChars / $text.Length) * 100, 1)
            $elapsed = (Get-Date) - $startTime
            $charsPerSec = if ($elapsed.TotalSeconds -gt 0) { [Math]::Round($typedChars / $elapsed.TotalSeconds, 1) } else { 0 }
            $progressLabel.Text = "$pct% - $typedChars / $($text.Length) chars - ${charsPerSec} chars/sec"
            [System.Windows.Forms.Application]::DoEvents()
        }
    }
    
    # Done
    $endTime = Get-Date
    $duration = $endTime - $startTime
    $durationStr = "{0:mm\:ss}" -f $duration
    
    [GlobalKeyboardHook]::Uninstall()
    
    # Save history
    $histEntry = @{
        Date       = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        Characters = $typedChars
        Total      = $text.Length
        Speed      = $delay
        Duration   = $durationStr
        Mistakes   = $mistakes
        Status     = if ($typedChars -eq $text.Length) { "Completed" } else { "Cancelled" }
        Preview    = $text.Substring(0, [Math]::Min(100, $text.Length))
    }
    $script:TypingHistory.Add($histEntry) | Out-Null
    Save-AppHistory
    
    # Restore UI
    $form.WindowState = "Normal"
    $form.Activate()
    $startButton.Enabled = $true
    $stopButton.Enabled = $false
    $pauseButton.Enabled = $false
    $textBox.ReadOnly = $false
    $settingsTabControl.Enabled = $true
    $script:IsTyping = $false
    
    if ($typedChars -eq $text.Length) {
        $progressBar.Value = $progressBar.Maximum
        $progressLabel.Text = "Complete! $typedChars chars in $durationStr"
        Update-StatusBar "Successfully typed $typedChars characters ($mistakes typos simulated) in $durationStr"
        [System.Media.SystemSounds]::Beep.Play()
    } else {
        $progressLabel.Text = "Stopped at $typedChars / $($text.Length) chars"
        Update-StatusBar "Typing stopped at $typedChars of $($text.Length) characters"
        [System.Media.SystemSounds]::Asterisk.Play()
    }
})

# ═══════════════════════════════════════════════════════════════
# KEYBOARD SHORTCUTS
# ═══════════════════════════════════════════════════════════════
$form.Add_KeyDown({
    if ($_.Control -and $_.KeyCode -eq "Return" -and $startButton.Enabled) {
        $startButton.PerformClick()
        $_.Handled = $true
    }
})

# ═══════════════════════════════════════════════════════════════
# FORM LIFECYCLE
# ═══════════════════════════════════════════════════════════════
$form.Add_FormClosing({
    if ($script:IsTyping) {
        [GlobalKeyboardHook]::EscapePressed = $true
        Start-Sleep -Milliseconds 200
    }
    [GlobalKeyboardHook]::Uninstall()
    Save-AppConfig
    if ($script:trayIcon) {
        $script:trayIcon.Visible = $false
        $script:trayIcon.Dispose()
    }
})

$form.Add_Shown({
    Load-AppProfiles
    Load-AppHistory
    Update-ProfileMenu
    Load-AppConfig
    Apply-Theme
    Update-SpeedDisplay
    Update-TextStats
})

# ═══════════════════════════════════════════════════════════════
# SYSTEM TRAY
# ═══════════════════════════════════════════════════════════════
$script:trayIcon = New-Object System.Windows.Forms.NotifyIcon
$script:trayIcon.Text = "Ghost Typer Pro"
$script:trayIcon.Visible = $false
try { $script:trayIcon.Icon = $form.Icon } catch {}

$trayMenu = New-Object System.Windows.Forms.ContextMenuStrip
$trayShowItem = New-Object System.Windows.Forms.ToolStripMenuItem("Show")
$trayShowItem.Add_Click({
    $form.Show()
    $form.WindowState = "Normal"
    $form.Activate()
    $script:trayIcon.Visible = $false
})
$trayMenu.Items.Add($trayShowItem) | Out-Null

$trayExitItem = New-Object System.Windows.Forms.ToolStripMenuItem("Exit")
$trayExitItem.Add_Click({ $form.Close() })
$trayMenu.Items.Add($trayExitItem) | Out-Null

$script:trayIcon.ContextMenuStrip = $trayMenu

$script:trayIcon.Add_DoubleClick({
    $form.Show()
    $form.WindowState = "Normal"
    $form.Activate()
    $script:trayIcon.Visible = $false
})

$form.Add_Resize({
    if ($form.WindowState -eq "Minimized" -and -not $script:IsTyping) {
        $script:trayIcon.Visible = $true
        $script:trayIcon.ShowBalloonTip(1000, "Ghost Typer Pro", "Minimized to tray", "Info")
        $form.Hide()
    }
})

# ═══════════════════════════════════════════════════════════════
# LAUNCH
# ═══════════════════════════════════════════════════════════════
[void]$form.ShowDialog()
