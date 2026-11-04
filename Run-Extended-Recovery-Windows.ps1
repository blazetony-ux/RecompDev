# Optional, long-running integration check for the original C++ recovery service.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
& py -3 (Join-Path $PSScriptRoot 'modular\tests\test_integration.py') 'TestRealLegacyServices.test_real_recovery_invoked_with_authenticated_pcode' -v
if ($LASTEXITCODE -ne 0) { throw 'Extended v0.4.2 native recovery test failed; production installation untouched.' }
