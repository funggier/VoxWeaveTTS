// Minimal launcher for the independent Windows Client Portable ZIP.
// Starts only the Tk remote API controller, never the TTS server.
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class VoxWeaveRemoteClientLauncher
{
    [STAThread]
    internal static void Main()
    {
        try
        {
            string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
            string python = Path.Combine(root, @"runtime\python\pythonw.exe");
            string client = Path.Combine(root, @"src\voxweavetts\remote_client.py");
            if (!File.Exists(python) || !File.Exists(client))
                throw new FileNotFoundException("Portable Python or Client code is missing");
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = python;
            info.Arguments = "-m voxweavetts.remote_client";
            info.WorkingDirectory = root;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.EnvironmentVariables["PYTHONPATH"] = Path.Combine(root, "src");
            info.EnvironmentVariables["PYTHONNOUSERSITE"] = "1";
            info.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"] = "1";
            Process.Start(info);
        }
        catch (Exception)
        {
            MessageBox.Show("The portable Client is incomplete. Re-extract the ZIP.",
                            "VoxWeaveTTS Client", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
