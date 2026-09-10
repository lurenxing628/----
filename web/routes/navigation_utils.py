"""Compatibility exports; implementation lives in web.routes.helpers.navigation_utils."""

from web.routes.helpers.navigation_utils import (
    Optional as Optional,
)
from web.routes.helpers.navigation_utils import (
    _safe_next_url as _safe_next_url,
)
from web.routes.helpers.navigation_utils import (
    _safe_next_url_core as _safe_next_url_core,
)
from web.routes.helpers.navigation_utils import (
    _same_origin_absolute_to_relative as _same_origin_absolute_to_relative,
)
from web.routes.helpers.navigation_utils import (
    _warn_invalid_next_url_once as _warn_invalid_next_url_once,
)
from web.routes.helpers.navigation_utils import (
    current_app as current_app,
)
from web.routes.helpers.navigation_utils import (
    g as g,
)
from web.routes.helpers.navigation_utils import (
    request as request,
)
from web.routes.helpers.navigation_utils import (
    safe_log as safe_log,
)
from web.routes.helpers.navigation_utils import (
    url_for as url_for,
)
from web.routes.helpers.navigation_utils import (
    urlparse as urlparse,
)
