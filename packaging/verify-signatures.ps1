param(
  [Parameter(Mandatory = $true)]
  [string[]]$Path
)

$ErrorActionPreference = 'Stop'

foreach ($Candidate in $Path) {
  if (-not (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
    throw "Signed file was not found: $Candidate"
  }

  $Signature = Get-AuthenticodeSignature -LiteralPath $Candidate
  if ($Signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    throw "Authenticode signature is not valid for $Candidate. Status: $($Signature.Status); $($Signature.StatusMessage)"
  }
  if (-not $Signature.SignerCertificate) {
    throw "Signer certificate is missing for $Candidate"
  }
  if (-not $Signature.TimeStamperCertificate) {
    throw "Trusted timestamp is missing for $Candidate"
  }

  [pscustomobject]@{
    Path = (Resolve-Path -LiteralPath $Candidate).Path
    Status = $Signature.Status
    Signer = $Signature.SignerCertificate.Subject
    TimestampAuthority = $Signature.TimeStamperCertificate.Subject
  }
}
