// VoxWeaveTTS Windows Portable launcher: manages one local Python server.
// Compiles with the Windows .NET Framework C# compiler (no extra SDK required).
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Windows.Forms;

internal sealed class VoxWeaveLauncher : Form
{
    private readonly string root;
    private readonly string url = "http://127.0.0.1:8765/";
    private Process server;
    private readonly Timer timer = new Timer();
    private readonly Label status = new Label();
    private readonly Button open = new Button();
    private readonly Button overlay = new Button();
    private readonly Button exit = new Button();
    private bool opened = false;
    private int checks = 0;

    public VoxWeaveLauncher()
    {
        root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
        Text = "VoxWeaveTTS — Windows Portable";
        Width = 570;
        Height = 250;
        MinimumSize = new Size(500, 245);
        MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Color.White;
        Font = new Font("Segoe UI", 10.0f);
        FormBorderStyle = FormBorderStyle.FixedDialog;

        Label header = new Label();
        header.Text = "VoxWeaveTTS";
        header.Font = new Font("Segoe UI", 21.0f, FontStyle.Bold);
        header.Location = new Point(24, 20);
        header.AutoSize = true;
        Controls.Add(header);

        Label subtitle = new Label();
        subtitle.Text = "Local Thai TTS  •  Firefox / Chrome  •  127.0.0.1:8765";
        subtitle.Location = new Point(26, 68);
        subtitle.Size = new Size(500, 24);
        Controls.Add(subtitle);

        status.Location = new Point(26, 104);
        status.Size = new Size(512, 34);
        status.Text = "Starting the local server...";
        Controls.Add(status);

        open.Text = "Open App";
        open.SetBounds(24, 151, 155, 37);
        open.Enabled = false;
        open.Click += delegate { OpenUrl(url); };
        Controls.Add(open);

        overlay.Text = "OBS Overlay";
        overlay.SetBounds(192, 151, 155, 37);
        overlay.Enabled = false;
        overlay.Click += delegate { OpenUrl(url + "overlay"); };
        Controls.Add(overlay);

        exit.Text = "Stop && Exit";
        exit.SetBounds(360, 151, 164, 37);
        exit.Click += delegate { Close(); };
        Controls.Add(exit);

        Shown += delegate { StartServer(); };
        FormClosing += delegate { StopServer(); };
    }

    private bool PortInUse()
    {
        try
        {
            using (TcpClient client = new TcpClient())
            {
                IAsyncResult result = client.BeginConnect("127.0.0.1", 8765, null, null);
                bool ok = result.AsyncWaitHandle.WaitOne(180);
                if (ok) client.EndConnect(result);
                return ok;
            }
        }
        catch { return false; }
    }

    private bool HealthReady()
    {
        try
        {
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(url + "v1/status");
            request.Timeout = 600;
            request.Proxy = null;
            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
            {
                if (response.StatusCode != HttpStatusCode.OK) return false;
                using (StreamReader reader = new StreamReader(response.GetResponseStream()))
                {
                    string body = reader.ReadToEnd();
                    return body.Contains("\"VoxWeaveTTS\"");
                }
            }
        }
        catch { return false; }
    }

    private void StartServer()
    {
        string python = Path.Combine(root, @"runtime\python\python.exe");
        if (!File.Exists(python) || !File.Exists(Path.Combine(root, @"src\voxweavetts\server.py")))
        {
            status.Text = "Portable runtime is incomplete; re-extract the ZIP.";
            return;
        }
        if (PortInUse())
        {
            status.Text = "Port 8765 is already in use. Close the other server first.";
            return;
        }
        try
        {
            foreach (string folder in new string[] {
                "cache", @"cache\temp", @"cache\huggingface", @"cache\torch",
                "data", "models", "voices", "output", "logs"
            })
                Directory.CreateDirectory(Path.Combine(root, folder));

            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = python;
            info.Arguments = "-m voxweavetts --port 8765";
            info.WorkingDirectory = root;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.EnvironmentVariables["PYTHONPATH"] = Path.Combine(root, "src");
            info.EnvironmentVariables["PYTHONNOUSERSITE"] = "1";
            info.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"] = "1";
            info.EnvironmentVariables["HF_HOME"] = Path.Combine(root, @"cache\huggingface");
            info.EnvironmentVariables["TORCH_HOME"] = Path.Combine(root, @"cache\torch");
            info.EnvironmentVariables["XDG_CACHE_HOME"] = Path.Combine(root, "cache");
            info.EnvironmentVariables["TEMP"] = Path.Combine(root, @"cache\temp");
            info.EnvironmentVariables["TMP"] = Path.Combine(root, @"cache\temp");
            server = Process.Start(info);
            timer.Interval = 600;
            timer.Tick += delegate {
                checks++;
                if (server == null || server.HasExited)
                {
                    timer.Stop();
                    status.Text = "Server stopped or failed. Check the portable package.";
                    return;
                }
                if (HealthReady())
                {
                    timer.Stop();
                    status.Text = "Ready. The app is available only on this computer.";
                    open.Enabled = true;
                    overlay.Enabled = true;
                    if (!opened) { opened = true; OpenUrl(url); }
                    return;
                }
                if (checks > 60)
                {
                    timer.Stop();
                    status.Text = "Server startup timed out. Check Windows firewall/settings.";
                }
            };
            timer.Start();
        }
        catch (Exception)
        {
            status.Text = "Unable to start local runtime. Re-extract the package.";
        }
    }

    private static void OpenUrl(string address)
    {
        try
        {
            ProcessStartInfo info = new ProcessStartInfo(address);
            info.UseShellExecute = true;
            Process.Start(info);
        }
        catch { MessageBox.Show("Could not open the default browser.", "VoxWeaveTTS"); }
    }

    private void StopServer()
    {
        timer.Stop();
        try
        {
            if (server != null && !server.HasExited)
            {
                server.Kill();
                server.WaitForExit(2500);
            }
        }
        catch {}
        finally { if (server != null) server.Dispose(); }
    }

    [STAThread]
    internal static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new VoxWeaveLauncher());
    }
}
