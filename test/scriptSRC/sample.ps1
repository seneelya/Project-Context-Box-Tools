# setup
param([string]$Name = "x")
$ErrorActionPreference = "Stop"

<# block
   comment #>
function Get-Thing {
    param($a)
    foreach ($i in 1..3) {
        Write-Host $i
    }
    try {
        Do-It
    } catch {
        Write-Warning $_
    } finally {
        Done
    }
}

class Box {
    [int]$Size
    Box([int]$s) { $this.Size = $s }
    [int] Area() {
        return $this.Size * $this.Size
    }
}

switch ($Name) {
    "a" { Write-Host a }
    default { Write-Host d }
}
Get-Thing -a 1
