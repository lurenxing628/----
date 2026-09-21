"""Shared resource capacity kernel.

One definition of calendars, working windows and occupancy metrics for every caller
(workbench projections, reports and exports). It sits below both so that neither
package has to import the other: see
docs/dev/decisions/2026-09-16-decision-capacity-kernel-package.md
"""
