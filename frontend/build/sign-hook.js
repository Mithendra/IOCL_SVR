// electron-builder `win.sign` hook (referenced from package.json > build.win.sign).
//
// electron-builder calls this once per PE file it produces (the app .exe, the
// uninstaller, the NSIS installer). We delegate to installer/sign.ps1, the single
// mechanism switch shared with the frozen-backend signing step. With no cert
// configured, sign.ps1 no-ops and exits 0, so an unsigned build still succeeds.

const { execFileSync } = require("node:child_process");
const path = require("node:path");

const SIGN_PS1 = path.resolve(__dirname, "..", "..", "installer", "sign.ps1");

exports.default = async function sign(configuration) {
  const file = configuration.path;
  if (!file) return;
  execFileSync(
    "powershell.exe",
    [
      "-NoProfile",
      "-NonInteractive",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      SIGN_PS1,
      "-Path",
      file,
    ],
    { stdio: "inherit" },
  );
};
