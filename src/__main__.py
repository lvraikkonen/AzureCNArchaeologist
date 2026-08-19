"""Allow ``python -m src`` from the project checkout."""

from .cli import main


raise SystemExit(main())
