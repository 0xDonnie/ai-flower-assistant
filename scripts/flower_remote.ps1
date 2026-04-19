# Flower Remote — mini PowerShell GUI that sends gesture triggers to the Pi.
# Usage: double-click the file (or from PowerShell: .\flower_remote.ps1)
# Requirement: SSH key configured on the Pi (no password prompt).

# TODO: set PI_HOST to your Pi's user@hostname-or-ip
Add-Type -AssemblyName PresentationFramework

$PI_HOST = "pi@your-flower.local"

function Send-Command {
    param($cmd)
    Start-Job -ScriptBlock {
        param($h, $c)
        ssh $h "echo $c > /tmp/flower-command" 2>&1 | Out-Null
    } -ArgumentList $PI_HOST, $cmd | Out-Null
}

function Send-Shutdown {
    $confirm = [System.Windows.MessageBox]::Show(
        "Shut down the Raspberry Pi?",
        "Flower — Shutdown",
        [System.Windows.MessageBoxButton]::YesNo,
        [System.Windows.MessageBoxImage]::Warning)
    if ($confirm -eq [System.Windows.MessageBoxResult]::Yes) {
        Start-Job -ScriptBlock {
            param($h)
            ssh -o StrictHostKeyChecking=no $h "sudo shutdown -h now" 2>&1 | Out-Null
        } -ArgumentList $PI_HOST | Out-Null
    }
}

$iconPath = Join-Path (Split-Path -Parent $PSScriptRoot) "docs/images/flower.ico"
$iconUri = if (Test-Path $iconPath) { (New-Object System.Uri($iconPath)).AbsoluteUri } else { "" }

[xml]$xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        Title="Flower Remote" Height="420" Width="300"
        WindowStartupLocation="CenterScreen" ResizeMode="NoResize"
        Background="#FFEAF5D2"
        Icon="$iconUri">
    <Grid Margin="12">
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>
        <TextBlock Grid.Row="0" Text="Flower Remote"
                   FontSize="20" FontWeight="Bold"
                   HorizontalAlignment="Center" Margin="0,0,0,12"
                   Foreground="#FF2F6B1F"/>
        <StackPanel Grid.Row="1">
            <Button Name="BtnTap"  Content="Tap - random quip"              Height="38" Margin="0,4" FontSize="13"/>
            <Button Name="BtnTap2" Content="2x Tap - toggle idle chatter"   Height="38" Margin="0,4" FontSize="13"/>
            <Button Name="BtnTap3" Content="3x Tap - reset memory"          Height="38" Margin="0,4" FontSize="13"/>
            <Button Name="BtnTap4" Content="4x Tap - music mode"            Height="38" Margin="0,4" FontSize="13"/>
            <Button Name="BtnTap5" Content="5x Tap - special message"       Height="38" Margin="0,4" FontSize="13"/>
            <Button Name="BtnHold" Content="Hold - push-to-talk (record)"   Height="38" Margin="0,4" FontSize="13"/>
        </StackPanel>
        <Button Grid.Row="2" Name="BtnShutdown" Content="Shutdown Pi"
                Height="36" Margin="0,16,0,0" FontSize="13" FontWeight="Bold"
                Background="#FFB03030" Foreground="White"/>
    </Grid>
</Window>
"@

$reader = New-Object System.Xml.XmlNodeReader $xaml
$window = [Windows.Markup.XamlReader]::Load($reader)

$window.FindName("BtnTap").Add_Click({  Send-Command "tap"  })
$window.FindName("BtnTap2").Add_Click({ Send-Command "tap2" })
$window.FindName("BtnTap3").Add_Click({ Send-Command "tap3" })
$window.FindName("BtnTap4").Add_Click({ Send-Command "tap4" })
$window.FindName("BtnTap5").Add_Click({ Send-Command "tap5" })
$window.FindName("BtnHold").Add_Click({ Send-Command "hold" })
$window.FindName("BtnShutdown").Add_Click({ Send-Shutdown })

$window.ShowDialog() | Out-Null
