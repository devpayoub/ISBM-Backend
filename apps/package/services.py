from apps.accounts.models import ShiftAssignment


def resolve_personnel(machine, start, end=None):
    """Who worked at `machine` at any point during [start, end) — plan.md
    §9's "personnel who worked at the machine to produce the bottles in
    the bag." Reads ShiftAssignment (self-populating from login/logout),
    never guesses. When `end` is None (production_finished_at not known
    yet), this is a single-instant lookup at `start`, not a zero-width
    range — a zero-width [start, start) would match nothing even for an
    assignment that started at exactly that moment."""
    if end is None or end <= start:
        rows = ShiftAssignment.working_at(start, machine=machine)
    else:
        rows = ShiftAssignment.working_between(start, end, machine=machine)
    # Normal login/logout flow (clock_in/clock_out) never leaves more than
    # one open assignment per user, but overlapping rows are still possible
    # from edge cases (e.g. a manual data fix) — dedupe by user so the same
    # person never appears twice in one bag's snapshot.
    seen = {}
    for a in rows:
        if a.user_id and a.user_id not in seen:
            seen[a.user_id] = {"id": a.user_id, "name": a.user.full_name, "role": a.user.role}
    return list(seen.values())
