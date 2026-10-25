<#
Deploy Pitchside to Azure Container Apps.

Run from the project folder, after `az login`:
    .\scripts\deploy_azure.ps1 -ResourceGroup pitchside-rg -Location centralindia

It builds the image in Azure from the Dockerfile (no local Docker needed), reads your .env,
stores the two API keys as Container Apps secrets, and passes the other settings as plain
environment variables. Secret values are never printed.

It keeps exactly one replica running: the guardrail counters live in memory, so a second
replica would double the cloud budget.
#>
param(
    [string]$ResourceGroup = "pitchside-rg",
    [string]$Location = "centralindia",
    [string]$Name = "pitchside"
)

$ErrorActionPreference = "Stop"

function Invoke-Az {
    & az @args
    if ($LASTEXITCODE -ne 0) { throw "az $($args[0]) $($args[1]) failed (exit code $LASTEXITCODE)" }
}

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI not found. Install it with: winget install -e --id Microsoft.AzureCLI"
}

$root = Join-Path $PSScriptRoot ".."
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) { throw "No .env found at $envFile" }

$vars = @{}
foreach ($raw in Get-Content $envFile) {
    $line = $raw.Trim()
    if (-not $line -or $line.StartsWith("#")) { continue }
    $idx = $line.IndexOf("=")
    if ($idx -lt 1) { continue }
    $vars[$line.Substring(0, $idx).Trim()] = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
}

foreach ($required in "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT") {
    if (-not $vars[$required]) { throw "$required is empty in .env" }
}

# Which .env keys become secrets (value = secret name) and which stay plain settings.
$secretNames = @{
    "AZURE_OPENAI_API_KEY"  = "openai-key"
    "AZURE_TRANSLATOR_KEY"  = "translator-key"
}
$plainKeys = @(
    "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_TRANSLATOR_REGION", "AZURE_TRANSLATOR_ENDPOINT"
)

$secretArgs = @()
$envArgs = @()
foreach ($key in $vars.Keys) {
    if (-not $vars[$key]) { continue }
    if ($secretNames.ContainsKey($key)) {
        $secretArgs += "$($secretNames[$key])=$($vars[$key])"
        $envArgs += "$key=secretref:$($secretNames[$key])"
    }
    elseif ($plainKeys -contains $key -or $key -like "PITCHSIDE_*") {
        $envArgs += "$key=$($vars[$key])"
    }
}

Write-Host "Registering providers (safe to repeat)..."
$have = & az extension list --query "[?name=='containerapp'].name" -o tsv
if ($have) {
    Write-Host "Container Apps extension already installed."
}
else {
    Invoke-Az extension add --name containerapp --only-show-errors
}
Invoke-Az provider register --namespace Microsoft.App --only-show-errors
Invoke-Az provider register --namespace Microsoft.OperationalInsights --only-show-errors

Write-Host "Building and deploying (this takes a few minutes)..."
Invoke-Az containerapp up `
    --name $Name --resource-group $ResourceGroup --location $Location `
    --source $root `
    --ingress external --target-port 8000

Write-Host "Storing secrets and settings..."
Invoke-Az containerapp secret set --name $Name --resource-group $ResourceGroup --secrets @secretArgs
Invoke-Az containerapp update --name $Name --resource-group $ResourceGroup `
    --min-replicas 1 --max-replicas 1 --set-env-vars @envArgs

$fqdn = & az containerapp show --name $Name --resource-group $ResourceGroup `
    --query properties.configuration.ingress.fqdn -o tsv
Write-Host ""
Write-Host "Live at: https://$fqdn"
Write-Host "Check:   https://$fqdn/health"
