from apps.accounts.models import ShiftAssignment


def resolve_personnel(machine, when):
    """Who was working when — plan.md §6's automatic people lookup. Reads
    ShiftAssignment (self-populating from login/logout, see
    apps.accounts.ShiftAssignment.clock_in/clock_out), never guesses.
    `machine` may be None (site-wide lookup); `when` is a datetime."""
    rows = list(ShiftAssignment.working_at(when, machine=machine.pk if machine else None))

    def _names(role):
        # Dedupe by user — overlapping ShiftAssignment rows for the same
        # person shouldn't happen via normal login/logout, but a stray
        # duplicate must never make one person look like two.
        seen = {}
        for a in rows:
            if a.user_id and a.user.role == role and a.user_id not in seen:
                seen[a.user_id] = {"id": a.user_id, "name": a.user.full_name}
        return list(seen.values())

    hour_start = when.replace(minute=0, second=0, microsecond=0)
    return {
        "date": when.date().isoformat(),
        "hour_label": f"{hour_start:%H}:00-{hour_start:%H}:59",
        "shift": rows[0].shift if rows else "",
        "machine": machine.code if machine else "",
        "maintenance": _names("MAINTENANCE"),
        "controller": _names("CONTROLLER"),
        "production": _names("OPERATOR"),
    }
