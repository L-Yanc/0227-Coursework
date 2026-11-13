# Part 4 results

Reference: approximate COLMAP reconstruction, scaled with the 1.005 m wall pair; 0.5 m pair held out. See reference_quality.json and marker_scale.json.

{
  "selected_method_complete": true,
  "standard_sequences_configured": true,
  "own_attempts_completed": true,
  "own_configurations": [
    {
      "method": "mono",
      "policy": "every",
      "attempts": 5,
      "scored_runs": 5,
      "complete": true
    },
    {
      "method": "pseudo_rgbd",
      "policy": "every",
      "attempts": 5,
      "scored_runs": 5,
      "complete": true
    },
    {
      "method": "pseudo_rgbd",
      "policy": "stride5",
      "attempts": 5,
      "scored_runs": 5,
      "complete": true
    },
    {
      "method": "selected",
      "policy": "every",
      "attempts": 5,
      "scored_runs": 5,
      "complete": true
    },
    {
      "method": "selected",
      "policy": "stride5",
      "attempts": 5,
      "scored_runs": 5,
      "complete": true
    },
    {
      "method": "selected",
      "policy": "keyframes",
      "attempts": 5,
      "scored_runs": 5,
      "complete": true
    },
    {
      "method": "selected_temporal",
      "policy": "keyframes",
      "attempts": 5,
      "scored_runs": 5,
      "complete": true
    }
  ],
  "standard_attempts_completed": true,
  "full_experiment_completed": true,
  "completion_means": "All requested repeated attempts executed; failed/unscored attempts remain explicit and are not counted as successful accuracy scores.",
  "evaluation_key": "5f1496a9320f1b6d021eac04b4d722dfdc50acb6d9c355c72af096f856ce95b5",
  "reference_quality_gate_passed": true,
  "known_limitations": [
    "Standard experiments must be run separately with run-standard or run-all",
    "Prediction timing unspecified by user",
    "COLMAP is an approximate reference"
  ]
}
