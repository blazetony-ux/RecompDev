#pragma once
// Reusable native DLL host, preserved from the previously tested harness.
// The compiled controller calls this directly: no Python or subprocess.
int rd_harness_run(int argc,char **argv);
