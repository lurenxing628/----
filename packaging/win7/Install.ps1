#Requires -Version 2.0
# ASCII source; supported on the original Win7 PowerShell 2.0 environment.
param([string]$Destination='',[switch]$VerifyOnly,[switch]$NoOpen)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetDirectoryName($MyInvocation.MyCommand.Path)
function Hash([string]$Path){
 $stream=[IO.File]::OpenRead($Path);$algorithm=New-Object Security.Cryptography.SHA256Managed
 try{return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant()}
 finally{$stream.Close();$algorithm.Clear()}
}
function Child([string]$Parent,[string]$Relative){
 if([IO.Path]::IsPathRooted($Relative) -or $Relative.Contains(':') -or ($Relative -split '[/\\]') -contains '..'){throw 'Unsafe package path'}
 $result=[IO.Path]::GetFullPath((Join-Path $Parent $Relative))
 if(-not $result.StartsWith(([IO.Path]::GetFullPath($Parent).TrimEnd('\')+'\'),[StringComparison]::OrdinalIgnoreCase)){throw 'Package path escaped its root'}
 return $result
}
function Check([string]$File,[string]$Digest,[long]$Length){
 if(-not(Test-Path -LiteralPath $File -PathType Leaf)){throw ('Missing file: '+$File)}
 if(((Get-Item -LiteralPath $File).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Link refused'}
 if((Get-Item -LiteralPath $File).Length -ne $Length -or (Hash $File) -cne $Digest){throw ('File is incomplete or damaged: '+$File)}
}
function ReadCsv([string]$File){return @([IO.File]::ReadAllText($File,[Text.Encoding]::UTF8)|ConvertFrom-Csv)}
try{
 $machine=Get-WmiObject Win32_OperatingSystem
 if([string]$machine.OSArchitecture -notmatch '64'){throw 'Windows x64 is required'}
 $version=[Version]$machine.Version
 if($version -lt [Version]'6.1' -or ($version -eq [Version]'6.1.7600')){throw 'Windows 7 SP1 x64 or newer is required'}
 if(-not $Destination){$Destination=Join-Path $root 'Application'}
 $Destination=[IO.Path]::GetFullPath($Destination)
 # Refuse existing targets before writing or extracting anything into them.
 if(-not $VerifyOnly -and (Test-Path -LiteralPath $Destination)){throw ('Destination already exists; choose a NEW folder. Existing data was not changed: '+$Destination)}
 $support=ReadCsv (Join-Path $root 'support.csv')
 foreach($row in $support){Check (Child $root $row.Path) $row.SHA256 ([long]$row.Bytes)}
 $tool=Join-Path $root 'tools\7za.exe'
 $parts=ReadCsv (Join-Path $root 'parts.csv')
 if($parts.Count -eq 0){throw 'Package parts manifest is empty'}
 foreach($part in $parts){
  $piece=Child $root $part.Path
  if(-not(Test-Path -LiteralPath $piece)){
   if(-not $part.Zip){throw ('Missing first package part: '+$part.Path)}
   $zip=$null
   foreach($directory in @($root,[IO.Path]::GetDirectoryName($root))){
    $candidate=Child $directory $part.Zip
    if(Test-Path -LiteralPath $candidate){$zip=$candidate;break}
   }
   if(-not $zip){throw ('Put ALL ZIP packages together, then run Install.cmd again. Missing: '+$part.Zip)}
   Check $zip $part.ZipSHA256 ([long]$part.ZipBytes)
   & $tool x $zip $part.Path ('-o'+$root) -aos -y -bsp0
   if($LASTEXITCODE -ne 0){throw 'Could not read the additional ZIP package'}
  }
  Check $piece $part.SHA256 ([long]$part.Bytes)
 }
 $first=Child $root $parts[0].Path
 & $tool t $first -bsp0
 if($LASTEXITCODE -ne 0){throw 'Compressed payload integrity check failed'}
 if($VerifyOnly){Write-Output 'PASS: all package parts and compressed payload verified.';exit 0}
 Write-Output ('Extracting the complete offline application to: '+$Destination)
 & $tool x $first ('-o'+$Destination) -aos -y -bsp0
 if($LASTEXITCODE -ne 0){throw 'Extraction failed; original user data was not modified'}
 $app=Child $Destination 'APS_Portable'
 $files=ReadCsv (Join-Path $root 'files.csv')
 if($files.Count -lt 100){throw 'Application file manifest is incomplete'}
 foreach($row in $files){Check (Child $app $row.Path) $row.SHA256 ([long]$row.Bytes)}
 $actual=@(Get-ChildItem -LiteralPath $app -Recurse -Force|Where-Object {-not $_.PSIsContainer})
 if($actual.Count -ne $files.Count){throw 'Unexpected application files were found'}
 if(Test-Path -LiteralPath (Join-Path $app 'user-data')){throw 'A new package must not contain user data'}
 $launcher=@(Get-ChildItem -LiteralPath $app -Filter '*.bat')
 if($launcher.Count -ne 1){throw 'Application launcher could not be identified uniquely'}
 [IO.File]::WriteAllText((Join-Path $Destination 'Start.cmd'),('@echo off'+"`r`n"+'setlocal DisableDelayedExpansion'+"`r`n"+'cd /d "%~dp0APS_Portable"'+"`r`n"+'for %%F in (*.bat) do call "%%F"'+"`r`n"),[Text.Encoding]::ASCII)
 [IO.File]::WriteAllText((Join-Path $root 'DEPLOYED.txt'),('Verified '+$files.Count+' original files. Start: '+(Join-Path $Destination 'Start.cmd')+"`r`n"))
 Write-Output ('SUCCESS: '+$files.Count+' files verified. Double-click Application\Start.cmd to use APS.')
 Write-Output 'No Python, browser installation, internet download or administrator installation is needed.'
 if(-not $NoOpen){Start-Process -FilePath 'explorer.exe' -ArgumentList ('"'+$Destination+'"')}
 exit 0
}catch{
 Write-Host ('ERROR: '+$_.Exception.Message) -ForegroundColor Red
 Write-Host 'Existing application folders and business data have not been overwritten.'
 exit 1
}
