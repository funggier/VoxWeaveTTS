// Original native v4 worker reference. Builds on Windows with .NET Framework csc.
// Emits a demonstration tone, not intelligible speech.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;

public static class Worker
{
    public static void Main(string[] args)
    {
        Console.InputEncoding = new UTF8Encoding(false);
        Console.OutputEncoding = new UTF8Encoding(false);
        var json = new JavaScriptSerializer { MaxJsonLength = 100000 };
        string line;
        while ((line = Console.ReadLine()) != null)
        {
            int id = 0;
            try
            {
                if (line.Length > 20000) throw new InvalidDataException();
                var input = json.Deserialize<Dictionary<string, object>>(line);
                id = Convert.ToInt32(input["request_id"]);
                if (Convert.ToInt32(input["version"]) != 1 ||
                    Convert.ToString(input["method"]) != "synthesize" ||
                    Convert.ToString(input["voice_id"]) != "native_tone")
                    throw new InvalidDataException();
                string text = Convert.ToString(input["text"]);
                if (String.IsNullOrWhiteSpace(text) || text.Length > 5000)
                    throw new InvalidDataException();
                double speed = Math.Max(0.6, Math.Min(5.0, Convert.ToDouble(input["speed"])));
                int frames = Math.Min(16000, (int)(7500 / speed) + text.Length * 110);
                int frequency = 280 + (text.Length % 12) * 25;
                byte[] pcm = new byte[frames * 2];
                for (int i = 0; i < frames; i++)
                {
                    double envelope = Math.Min(1.0, Math.Min(i / 400.0, (frames-i) / 400.0));
                    short v = (short)(4000 * envelope * Math.Sin(2 * Math.PI * frequency * i / 16000.0));
                    pcm[i * 2] = (byte)(v & 255);
                    pcm[i * 2 + 1] = (byte)((v >> 8) & 255);
                }
                Console.WriteLine(json.Serialize(new {
                    version = 1, request_id = id, ok = true, sample_rate = 16000,
                    pcm16_b64 = Convert.ToBase64String(pcm)
                }));
            }
            catch (Exception)
            {
                Console.WriteLine(json.Serialize(new {
                    version = 1, request_id = id, ok = false, error = "synthesis_failure"
                }));
            }
            Console.Out.Flush();
        }
    }
}
