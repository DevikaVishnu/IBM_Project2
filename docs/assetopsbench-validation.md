# AssetOpsBench validation: runs 607 and 620

This note uses two local deep-agent traces.  It does not infer private model
reasoning.  A trace fact is recorded only when it appears in a tool result or
the final answer.

## What these runs test

- **607:** one Chiller 6 lookup fails, a second generator fails, then the
  agent obtains pump failure modes.  This makes the unsupported jump visible:
  pump evidence does not establish a fact about Chiller 6.
- **620:** the agent obtains installed/measured sensors and a time extent.  It
  can support a sensor list and data coverage, but not that the sensors detect
  a chiller trip: no readings, trip labels, or test are recorded.

## Schema result

Keep `source_trace`, `produced_by`, `tool_status`, and evidence links.  They
explain both runs and make the 607 mistake inspectable.

`tool_error` and `attempt_number` are useful, but have appeared in only one
run so they remain candidates, not final core fields.

Do not add `delivers`, `checks`, delegation, or visibility fields because of
these files alone.  The exact rendered model prompts, reviews, and sub-agent
handoffs are absent, so those answers must remain `UNKNOWN`.
