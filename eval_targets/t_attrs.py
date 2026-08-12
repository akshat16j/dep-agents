import attrs

attrs.set_run_validators(False)

@attrs.define
class Point:
    x = attrs.field(default=0)
