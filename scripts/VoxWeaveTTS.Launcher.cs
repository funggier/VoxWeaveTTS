// VoxWeaveTTS Windows Portable launcher: manages one local Python server.
// Compiles with the Windows .NET Framework C# compiler (no extra SDK required).
using System;
using System.Diagnostics;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Net.NetworkInformation;
using System.Security.Cryptography;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal sealed class VoxWeaveLauncher : Form
{
    private readonly string root;
    private readonly string settingsPath;
    private string url;
    private string listenIp = "127.0.0.1";
    private int listenPort = 8765;
    private string accessCode = "";
    private readonly ComboBox networkMode = new ComboBox();
    private readonly ComboBox address = new ComboBox();
    private readonly NumericUpDown port = new NumericUpDown();
    private readonly TextBox code = new TextBox();
    private readonly JavaScriptSerializer serializer = new JavaScriptSerializer();
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
        settingsPath = Path.Combine(root, "data", "network.json");
        Text = "VoxWeaveTTS — Windows Portable";
        ClientSize = new Size(595, 342);
        AutoScaleMode = AutoScaleMode.Font;
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
        subtitle.Text = "Windows Portable";
        subtitle.Location = new Point(26, 68);
        subtitle.Size = new Size(500, 24);
        Controls.Add(subtitle);

        status.Location = new Point(26, 100);
        status.Size = new Size(552, 42);
        Controls.Add(status);

        Controls.Add(new Label { Text = "Network", Location = new Point(26, 146), AutoSize = true });
        Controls.Add(new Label { Text = "IPv4 address", Location = new Point(162, 146), AutoSize = true });
        Controls.Add(new Label { Text = "Port", Location = new Point(472, 146), AutoSize = true });
        networkMode.SetBounds(26, 169, 126, 28);
        networkMode.DropDownStyle = ComboBoxStyle.DropDownList;
        networkMode.Items.AddRange(new string[] {"Local", "LAN", "Tailnet", "All IPv4"});
        networkMode.SelectedIndexChanged += delegate { FillAddresses(); };
        Controls.Add(networkMode);
        address.SetBounds(162, 169, 298, 28);
        address.DropDownWidth = 480;
        address.SelectionChangeCommitted += delegate
        {
            AddressChoice selected = address.SelectedItem as AddressChoice;
            if (selected != null) BeginInvoke(new MethodInvoker(delegate { address.Text = selected.Ip; }));
        };
        Controls.Add(address);
        port.SetBounds(472, 169, 97, 28);
        port.Minimum = 1;
        port.Maximum = 65535;
        port.Value = 8765;
        Controls.Add(port);

        Controls.Add(new Label { Text = "Network login (user: voxweave)", Location = new Point(26, 210), AutoSize = true });
        code.SetBounds(26, 233, 386, 28);
        code.ReadOnly = true;
        Controls.Add(code);
        Button apply = new Button { Text = "Apply && Restart" };
        apply.SetBounds(423, 231, 146, 32);
        apply.Click += delegate { ApplySettings(); };
        Controls.Add(apply);

        open.Text = "Open App";
        open.SetBounds(26, 281, 165, 37);
        open.Enabled = false;
        open.Click += delegate { OpenUrl(url); };
        Controls.Add(open);

        overlay.Text = "OBS Overlay";
        overlay.SetBounds(204, 281, 165, 37);
        overlay.Enabled = false;
        overlay.Click += delegate { OpenUrl(url + "overlay"); };
        Controls.Add(overlay);

        exit.Text = "Stop && Exit";
        exit.SetBounds(382, 281, 187, 37);
        exit.Click += delegate { Close(); };
        Controls.Add(exit);

        networkMode.SelectedIndex = 0;
        timer.Interval = 600;
        timer.Tick += delegate { CheckServer(); };
        Shown += delegate
        {
            try { ReadSettings(); StartServer(); }
            catch { status.Text = "Invalid data/network.json. Enter an IPv4 address and port, then Apply."; }
        };
        FormClosing += delegate { StopServer(); };
    }

    private sealed class AddressChoice
    {
        public string Ip;
        public string Adapter;
        public bool Tailnet;
        public override string ToString() { return Ip + " — " + Adapter; }
    }

    private List<AddressChoice> Adapters()
    {
        List<AddressChoice> items = new List<AddressChoice>();
        foreach (NetworkInterface adapter in NetworkInterface.GetAllNetworkInterfaces())
        {
            if (adapter.OperationalStatus != OperationalStatus.Up) continue;
            bool tailscale = (adapter.Name + " " + adapter.Description)
                .IndexOf("Tailscale", StringComparison.OrdinalIgnoreCase) >= 0;
            foreach (UnicastIPAddressInformation unicast in adapter.GetIPProperties().UnicastAddresses)
            {
                IPAddress ip = unicast.Address;
                if (ip.AddressFamily != AddressFamily.InterNetwork || IPAddress.IsLoopback(ip)
                    || ip.GetAddressBytes()[0] == 169 && ip.GetAddressBytes()[1] == 254) continue;
                items.Add(new AddressChoice { Ip = ip.ToString(), Adapter = adapter.Name, Tailnet = tailscale });
            }
        }
        return items;
    }

    private void FillAddresses()
    {
        address.Items.Clear();
        int mode = networkMode.SelectedIndex;
        if (mode == 0 || mode == 3)
        {
            address.Text = mode == 0 ? "127.0.0.1" : "0.0.0.0";
            return;
        }
        foreach (AddressChoice choice in Adapters())
            if (choice.Tailnet == (mode == 2)) address.Items.Add(choice);
        address.Text = address.Items.Count == 1 ? ((AddressChoice)address.Items[0]).Ip : "";
        if (address.Items.Count == 0)
            status.Text = mode == 2 ? "Tailscale IPv4 not found. Connect Tailscale, then choose Tailnet again."
                                   : "Enter the IPv4 address of this computer on the LAN.";
    }

    private void ReadSettings()
    {
        if (File.Exists(settingsPath))
        {
            var settings = serializer.Deserialize<Dictionary<string, object>>(File.ReadAllText(settingsPath));
            listenIp = (string)settings["host"];
            listenPort = (int)settings["port"];
            if (settings.ContainsKey("access_code")) accessCode = (string)settings["access_code"];
        }
        ValidateAddress(listenIp, listenPort);
        if ((!IsLoopback(listenIp) || accessCode.Length > 0) && !ValidAccessCode(accessCode))
            throw new FormatException("Invalid network access code");
        int mode = IsLoopback(listenIp) ? 0 : listenIp == "0.0.0.0" ? 3 :
            Adapters().Exists(candidate => candidate.Ip == listenIp && candidate.Tailnet) ? 2 : 1;
        networkMode.SelectedIndex = mode;
        address.Text = listenIp;
        port.Value = listenPort;
        code.Text = IsLoopback(listenIp) ? "" : accessCode;
    }

    private static bool IsLoopback(string ip)
    {
        return IPAddress.IsLoopback(IPAddress.Parse(ip));
    }

    private static bool ValidAccessCode(string value)
    {
        if (String.IsNullOrEmpty(value) || value.Length < 16 || value.Length > 128) return false;
        foreach (char c in value)
            if (c < '!' || c > '~') return false;
        return true;
    }

    private static void ValidateAddress(string ip, int tcpPort)
    {
        IPAddress parsed;
        if (!IPAddress.TryParse(ip, out parsed) || parsed.AddressFamily != AddressFamily.InterNetwork
            || parsed.ToString() != ip || tcpPort < 1 || tcpPort > 65535
            || parsed.GetAddressBytes()[0] >= 224)
            throw new FormatException("Enter an IPv4 address and a port from 1 to 65535.");
    }

    private static string GenerateAccessCode()
    {
        byte[] bytes = new byte[24];
        using (RandomNumberGenerator generator = RandomNumberGenerator.Create())
            generator.GetBytes(bytes);
        return BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant();
    }

    private void ApplySettings()
    {
        string selectedIp = address.Text.Trim();
        int selectedPort = (int)port.Value;
        try
        {
            ValidateAddress(selectedIp, selectedPort);
            string password = accessCode;
            if (!IsLoopback(selectedIp) && !ValidAccessCode(password)) password = GenerateAccessCode();
            var settings = new Dictionary<string, object> {
                {"host", selectedIp}, {"port", selectedPort}, {"access_code", password}
            };
            Directory.CreateDirectory(Path.GetDirectoryName(settingsPath));
            string next = settingsPath + "." + Guid.NewGuid().ToString("N") + ".tmp";
            try
            {
                File.WriteAllText(next, serializer.Serialize(settings));
                if (File.Exists(settingsPath)) File.Replace(next, settingsPath, null);
                else File.Move(next, settingsPath);
            }
            finally { if (File.Exists(next)) File.Delete(next); }

            StopServer();
            listenIp = selectedIp;
            listenPort = selectedPort;
            accessCode = password;
            code.Text = IsLoopback(listenIp) ? "" : accessCode;
            StartServer();
        }
        catch (FormatException error) { status.Text = error.Message; }
        catch (IOException) { status.Text = "Could not save data/network.json."; }
        catch (UnauthorizedAccessException) { status.Text = "Could not save data/network.json."; }
    }

    private bool PortInUse()
    {
        try
        {
            using (TcpClient client = new TcpClient())
            {
                IAsyncResult result = client.BeginConnect(listenIp == "0.0.0.0" ? "127.0.0.1" : listenIp, listenPort, null, null);
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
        string browserIp = listenIp == "0.0.0.0" ? "127.0.0.1" : listenIp;
        url = "http://" + browserIp + ":" + listenPort + "/";
        checks = 0;
        opened = false;
        open.Enabled = false;
        overlay.Enabled = false;
        string python = Path.Combine(root, @"runtime\python\python.exe");
        if (!File.Exists(python) || !File.Exists(Path.Combine(root, @"src\voxweavetts\server.py")))
        {
            status.Text = "Portable runtime is incomplete; re-extract the ZIP.";
            return;
        }
        if (PortInUse())
        {
            status.Text = url + " is already in use. Choose a different port.";
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
            info.Arguments = "-m voxweavetts --host " + listenIp + " --port " + listenPort;
            info.EnvironmentVariables["VOXWEAVETTS_NETWORK_PASSWORD"] = accessCode;
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
            status.Text = "Starting " + url;
            timer.Start();
        }
        catch (Exception)
        {
            status.Text = "Unable to start local runtime. Re-extract the package.";
        }
    }

    private void CheckServer()
    {
        checks++;
        if (server == null || server.HasExited)
        {
            timer.Stop();
            status.Text = "Could not listen on " + listenIp + ":" + listenPort +
                ". Check that the IP belongs to this computer and the port is free.";
            return;
        }
        if (HealthReady())
        {
            timer.Stop();
            status.Text = "Listening at " + url;
            open.Enabled = true;
            overlay.Enabled = true;
            if (!opened) { opened = true; OpenUrl(url); }
            return;
        }
        if (checks > 60)
        {
            timer.Stop();
            status.Text = "Server startup timed out. Check the IP and Windows firewall.";
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
        finally { if (server != null) server.Dispose(); server = null; }
    }

    [STAThread]
    internal static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new VoxWeaveLauncher());
    }
}
