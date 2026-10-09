param([string]$Launcher,[string]$Root,[string]$Scenario)
$ErrorActionPreference='Stop'
. $Launcher
$script:Events=@()
$script:StopFails=$false
$script:Injection='complete'
$script:StartCode=0

function Stop-ApsApplication([string]$Directory){
 $script:Events+=('stop|'+$Directory)
 if($script:StopFails){throw 'Controlled runtime stop failure.'}
}

function Start-ApsApplication([string]$Directory){
 $script:Events+=('start|'+$Directory)
 return $script:StartCode
}

function Invoke-ApsProgram([string]$Directory,[string]$Arguments){
 $script:Events+=('inject|'+$Directory+'|'+$Arguments)
 [void][IO.Directory]::CreateDirectory((Join-Path $Directory 'user-data'))
 if($script:Injection -eq 'absent'){return 0}
 [IO.File]::WriteAllText((Join-Path $Directory 'user-data\sample-acceptance.json'),
  ('{"state":"'+$script:Injection+'","committed":true}'),[Text.Encoding]::UTF8)
 if($script:Injection -eq 'failed'){return 7}
 return 0
}

$codes=@()
switch($Scenario){
 'default' {$codes+=Invoke-ApsSelection $Root 'Start'}
 'enable-reopen-disable' {
  $codes+=Invoke-ApsSelection $Root 'SampleOn'
  $codes+=Invoke-ApsSelection $Root 'Start'
  $codes+=Invoke-ApsSelection $Root 'SampleOff'
 }
 'enable-twice' {
  $codes+=Invoke-ApsSelection $Root 'SampleOn'
  $codes+=Invoke-ApsSelection $Root 'SampleOn'
 }
 'disable-when-off' {$codes+=Invoke-ApsSelection $Root 'SampleOff'}
 'pending-on' {
  [IO.File]::WriteAllText((Join-Path $Root 'sample-enabled.txt'),'enabled')
  $sample=Copy-ApsSampleProgram $Root
  [void][IO.Directory]::CreateDirectory((Join-Path $sample 'user-data'))
  [IO.File]::WriteAllText((Join-Path $sample 'user-data\sample-acceptance.json'),'{"state":"pending"}')
  [IO.File]::Delete((Join-Path $sample 'assets\local.txt'))
  $codes+=Invoke-ApsSelection $Root 'SampleOn'
 }
 'stop-failed-on' {
  $script:StopFails=$true
  $codes+=Invoke-ApsSelection $Root 'SampleOn'
 }
 'stop-failed-off' {
  $codes+=Invoke-ApsSelection $Root 'SampleOn'
  $script:StopFails=$true
  $codes+=Invoke-ApsSelection $Root 'SampleOff'
 }
 'inject-failed-restore' {
  $script:Injection='failed'
  $codes+=Invoke-ApsSelection $Root 'SampleOn'
  $codes+=Invoke-ApsSelection $Root 'Start'
  $codes+=Invoke-ApsSelection $Root 'SampleOn'
  $codes+=Invoke-ApsSelection $Root 'SampleOff'
 }
 'inject-no-result-restore' {
  $script:Injection='absent'
  $codes+=Invoke-ApsSelection $Root 'SampleOn'
  $codes+=Invoke-ApsSelection $Root 'SampleOff'
 }
 'invalid-result' {
  [IO.File]::WriteAllText((Join-Path $Root 'sample-enabled.txt'),'enabled')
  $sample=Copy-ApsSampleProgram $Root
  [void][IO.Directory]::CreateDirectory((Join-Path $sample 'user-data'))
  [IO.File]::WriteAllText((Join-Path $sample 'user-data\sample-acceptance.json'),'{"committed":true}')
  $codes+=Invoke-ApsSelection $Root 'Start'
 }
 'start-failed' {
  $script:StartCode=9
  $codes+=Invoke-ApsSelection $Root 'SampleOn'
 }
 'invalid-manifest' {$codes+=Invoke-ApsSelection $Root 'SampleOn'}
 default {throw ('Unknown scenario: '+$Scenario)}
}
$result=@{codes=$codes;events=$script:Events;enabled=[IO.File]::Exists((Join-Path $Root 'sample-enabled.txt'))}
$result|ConvertTo-Json -Compress -Depth 5
