#Requires -Version 2.0
# ASCII source; the outer portable launcher selects an independent sample folder.
param([ValidateSet('Start','SampleOn','SampleOff')][string]$Mode='Start')
$ErrorActionPreference='Stop'

function Get-ApsApplicationPath([string]$Root,[bool]$Sample){
 if($Sample){return (Join-Path $Root 'sample-context\APS_Portable')}
 return (Join-Path $Root 'APS_Portable')
}

function Get-ApsProgram([string]$Directory){
 $executables=@([IO.Directory]::GetFiles($Directory,'*.exe')|Sort-Object|Where-Object {
  [IO.Path]::GetFileName($_) -notmatch '^(unins.*|chrome)\.exe$'
 })
 if($executables.Count -eq 0){throw ('APS executable is missing: '+$Directory)}
 return $executables[0]
}

function Invoke-ApsProgram([string]$Directory,[string]$Arguments){
 $info=New-Object Diagnostics.ProcessStartInfo
 $info.FileName=Get-ApsProgram $Directory
 $info.Arguments=$Arguments
 $info.WorkingDirectory=$Directory
 $info.UseShellExecute=$false
 $info.CreateNoWindow=$true
 $process=[Diagnostics.Process]::Start($info)
 try{$process.WaitForExit();return $process.ExitCode}
 finally{$process.Dispose()}
}

function Stop-ApsApplication([string]$Directory){
 $code=Invoke-ApsProgram $Directory ('--runtime-stop "'+$Directory+'" --stop-aps-chrome')
 if($code -ne 0){throw ('APS could not stop normally. The selected context was not changed. Exit code: '+$code)}
}

function Get-ApsStaticFile([string]$Parent,[string]$Relative){
 $parts=$Relative -split '[/\\]'
 if(-not $Relative -or [IO.Path]::IsPathRooted($Relative) -or $Relative.Contains(':') -or
  $parts -contains '..' -or $parts -contains '.' -or $parts[0] -ieq 'user-data'){
  throw ('The program file list contains a non-program path: '+$Relative)
 }
 return [IO.Path]::GetFullPath((Join-Path $Parent $Relative))
}

function Copy-ApsSampleProgram([string]$Root){
 $source=Get-ApsApplicationPath $Root $false
 $sample=Get-ApsApplicationPath $Root $true
 $rows=@([IO.File]::ReadAllText((Join-Path $Root 'files.csv'),[Text.Encoding]::UTF8)|ConvertFrom-Csv)
 if($rows.Count -eq 0){throw 'The program file list is empty.'}
 foreach($row in $rows){
  $original=Get-ApsStaticFile $source $row.Path
  $target=Get-ApsStaticFile $sample $row.Path
  [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
  if(-not [IO.File]::Exists($target)){[IO.File]::Copy($original,$target,$false)}
 }
 [IO.File]::WriteAllText((Join-Path $sample 'aps-complex-sample.txt'),"complex sample`r`n",[Text.Encoding]::ASCII)
 return $sample
}

function Read-ApsSampleState([string]$Directory){
 $report=Join-Path $Directory 'user-data\sample-acceptance.json'
 if(-not [IO.File]::Exists($report)){return ''}
 $reader=Join-Path $Directory 'aps-launcher.ps1'
 . $reader
 try{
  $result=Read-ApsJson ([IO.File]::ReadAllText($report,[Text.Encoding]::UTF8))
  $state=[string](Get-ApsValue $result 'state')
  if(-not $state){throw 'The sample result has no state.'}
  return $state
 }catch{throw ('Sample result could not be read. Keep the report and use SampleOff.cmd to return: '+$report)}
}

function Start-ApsApplication([string]$Directory){
 . (Join-Path $Directory 'aps-launcher.ps1')
 return (Invoke-ApsLauncher $Directory)
}

function Start-ApsSelectedApplication([string]$Directory,[bool]$Sample){
 $state=''
 if($Sample){
  $state=Read-ApsSampleState $Directory
  if($state -and $state -ne 'complete'){
   throw ('Sample state: '+$state+'. Its progress/result is preserved at '+
    (Join-Path $Directory 'user-data\sample-acceptance.json')+'. Use SampleOff.cmd to return to your original data.')
  }
 }
 $code=Start-ApsApplication $Directory
 if($code -ne 0){return $code}
 if($Sample -and $state -ne 'complete'){
  Write-Host 'Creating and scheduling the independent complex sample. Please wait...'
  $code=Invoke-ApsProgram $Directory '--sample-inject'
  if($code -ne 0){throw ('Sample injection failed. Its report is preserved. Use SampleOff.cmd to return. Exit code: '+$code)}
  if((Read-ApsSampleState $Directory) -ne 'complete'){
   throw 'Sample injection did not report completion. Use SampleOff.cmd to return.'
  }
  Write-Host 'Sample injection completed. Refresh the APS page to see the sample.'
 }
 return 0
}

function Invoke-ApsSelection([string]$Root,[string]$Selection){
 try{
  $root=[IO.Path]::GetFullPath($Root)
  $switchFile=Join-Path $root 'sample-enabled.txt'
  $sample=[IO.File]::Exists($switchFile)
  $current=Get-ApsApplicationPath $root $sample
  if($Selection -eq 'SampleOn'){
   if($sample){return (Start-ApsSelectedApplication $current $true)}
   Stop-ApsApplication $current
   $target=Copy-ApsSampleProgram $root
   [IO.File]::WriteAllText($switchFile,"enabled`r`n",[Text.Encoding]::ASCII)
   $sample=$true
  }elseif($Selection -eq 'SampleOff'){
   if(-not $sample){return (Start-ApsSelectedApplication $current $false)}
   Stop-ApsApplication $current
   [IO.File]::Delete($switchFile)
   $target=Get-ApsApplicationPath $root $false
   $sample=$false
  }else{$target=$current}
  return (Start-ApsSelectedApplication $target $sample)
 }catch{
  Write-Host ('ERROR: '+$_.Exception.Message) -ForegroundColor Red
  return 1
 }
}

if($MyInvocation.InvocationName -ne '.'){
 exit (Invoke-ApsSelection ([IO.Path]::GetDirectoryName($MyInvocation.MyCommand.Path)) $Mode)
}
