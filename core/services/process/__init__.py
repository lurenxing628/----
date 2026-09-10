"""Process services; import each service from its defining module.

The package stays lightweight so shared policies do not load route parsing or
Excel conversion services while their own dependencies are being imported.
"""
