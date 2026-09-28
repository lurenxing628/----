using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Threading;

// External acceptance helper. Uses the package's SQLite library and opens only
// an owned synthetic slot, read-only. sqlite3_backup provides a consistent copy.
public static class Win7ReadOnlySnapshot {
    [DllImport("sqlite3.dll", CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_open_v2(string path, out IntPtr db, int flags, IntPtr vfs);
    [DllImport("sqlite3.dll", CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_close(IntPtr db);
    [DllImport("sqlite3.dll", CallingConvention=CallingConvention.Cdecl)] static extern IntPtr sqlite3_backup_init(IntPtr dest, string destName, IntPtr source, string sourceName);
    [DllImport("sqlite3.dll", CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_backup_step(IntPtr backup, int pages);
    [DllImport("sqlite3.dll", CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_backup_finish(IntPtr backup);
    [DllImport("sqlite3.dll", CallingConvention=CallingConvention.Cdecl)] static extern IntPtr sqlite3_errmsg(IntPtr db);
    static void Check(int code, IntPtr db) {
        if(code != 0) throw new Exception("SQLite " + code + ": " + Marshal.PtrToStringAnsi(sqlite3_errmsg(db)));
    }
    public static int Main(string[] args) {
        IntPtr source = IntPtr.Zero, dest = IntPtr.Zero, backup = IntPtr.Zero;
        try {
            string root = @"C:\APS-Workflows-20260927";
            if(File.ReadAllText(Path.Combine(root,"acceptance-owned.txt")) != "APS-WIN7-WORKFLOWS-20260927") throw new Exception("Ownership mismatch");
            if(args.Length != 2) throw new Exception("Expected slot and unique snapshot id");
            string[] slots = {"functional-d1307cb8","browser-d1307cb8","installed-d1307cb8","pressure1000-d1307cb8","pressure5000-d1307cb8"};
            if(Array.IndexOf(slots,args[0]) < 0) throw new Exception("Unknown isolated slot");
            Guid id; if(!Guid.TryParseExact(args[1],"N",out id)) throw new Exception("Invalid snapshot id");
            string input = Path.Combine(root,args[0],@"user-data\db\aps.db");
            string directory = @"\\vmware-host\Shared Folders\APSWorkflows20260927\snapshots";
            Directory.CreateDirectory(directory);
            string output = Path.Combine(directory,id.ToString("N") + ".db");
            if(!File.Exists(input) || File.Exists(output)) throw new Exception("Missing source or existing output");
            Check(sqlite3_open_v2(input,out source,1,IntPtr.Zero),source);
            Check(sqlite3_open_v2(output,out dest,6,IntPtr.Zero),dest);
            backup = sqlite3_backup_init(dest,"main",source,"main");
            if(backup == IntPtr.Zero) throw new Exception("Cannot open SQLite backup");
            Stopwatch timer = Stopwatch.StartNew();
            int status;
            do {
                status = sqlite3_backup_step(backup,128);
                if(status == 5 || status == 6) Thread.Sleep(50);
                else if(status != 0 && status != 101) Check(status,dest);
                if(timer.ElapsedMilliseconds > 30000) throw new Exception("Snapshot timed out");
            } while(status != 101);
            int finished = sqlite3_backup_finish(backup); backup = IntPtr.Zero; Check(finished,dest);
            Check(sqlite3_close(dest),dest); dest = IntPtr.Zero;
            Check(sqlite3_close(source),source); source = IntPtr.Zero;
            using(SHA256 sha = SHA256.Create()) using(FileStream stream = File.OpenRead(output)) {
                string digest = BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant();
                File.WriteAllText(output + ".sha256",digest);
                Console.WriteLine(digest + " " + new FileInfo(output).Length);
            }
            return 0;
        } catch(Exception error) { Console.Error.WriteLine(error.ToString()); return 1; }
        finally {
            if(backup != IntPtr.Zero) sqlite3_backup_finish(backup);
            if(dest != IntPtr.Zero) sqlite3_close(dest);
            if(source != IntPtr.Zero) sqlite3_close(source);
        }
    }
}
