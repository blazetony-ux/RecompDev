[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Rom,[string]$Catalogue='',[string]$Output='',[int]$Budget=150)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$argsList=@('-3',(Join-Path $root 'modular\cli.py'),'compare-discovery','--rom',$Rom,'--budget',[string]$Budget)
if($Catalogue){$argsList+=@('--catalogue',$Catalogue)}
if($Output){$argsList+=@('--out',$Output)}
& py @argsList
if ($LASTEXITCODE -ne 0) { throw "The original/modular comparison failed (exit $LASTEXITCODE)." }
