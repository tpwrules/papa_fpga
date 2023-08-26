set module [lindex $quartus(args) 0]
set project [lindex $quartus(args) 1]

if [string match "quartus_map" $module] {
    post_message "Running after mapping..."

    set where [file dirname [info script]]
    set quartus(args) [list $project]
    source [file join $where soc_system/synthesis/submodules/hps_sdram_p0_parameters.tcl]
    source [file join $where soc_system/synthesis/submodules/hps_sdram_p0_pin_assignments.tcl]
}
