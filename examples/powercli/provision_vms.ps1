# PowerCLI VM Provisioning Script
# Provisions VMs for Cloud-Native Infrastructure (Load Balancers, K8s, Ceph)

$vCenter = "vcenter.local"
$Datacenter = "Production-DC"
$Cluster = "K8s-Ceph-Cluster"
$Datastore = "vsanDatastore"
$TemplateName = "ubuntu-24-04-golden-template"
$NetworkName = "K8s-VM-Network"

Connect-VIServer -Server $vCenter -WarningAction SilentlyContinue

$VMs = @(
    @{ Name = "lb-node-01"; CPU = 2; RAM = 4GB },
    @{ Name = "lb-node-02"; CPU = 2; RAM = 4GB },
    @{ Name = "k8s-master-01"; CPU = 4; RAM = 8GB },
    @{ Name = "k8s-master-02"; CPU = 4; RAM = 8GB },
    @{ Name = "k8s-master-03"; CPU = 4; RAM = 8GB },
    @{ Name = "k8s-worker-01"; CPU = 4; RAM = 16GB },
    @{ Name = "k8s-worker-02"; CPU = 4; RAM = 16GB },
    @{ Name = "ceph-node-01"; CPU = 4; RAM = 8GB },
    @{ Name = "ceph-node-02"; CPU = 4; RAM = 8GB },
    @{ Name = "ceph-node-03"; CPU = 4; RAM = 8GB }
)

foreach ($VM in $VMs) {
    Write-Host "Deploying clone for $($VM.Name)..." -ForegroundColor Green
    $NewVM = New-VM -Name $VM.Name -Template $TemplateName -ResourcePool $Cluster -Datastore $Datastore -DiskStorageFormat Thin -Confirm:$false
    Set-VM -VM $NewVM -NumCpu $VM.CPU -MemoryGB ([math]::Round($VM.RAM / 1GB)) -Confirm:$false
    Get-NetworkAdapter -VM $NewVM | Set-NetworkAdapter -NetworkName $NetworkName -Confirm:$false
    Start-VM -VM $NewVM -Confirm:$false
}

Disconnect-VIServer -Confirm:$false