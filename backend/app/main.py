# (PATCHED CORS SECTION ONLY — replace existing CORS block)

# 4. CORS — production-safe but Vercel-friendly
_DEV_ORIGINS = ["http://localhost:3000", "http://localhost:8000"]

if settings.ENVIRONMENT == "production":
    _CORS_ORIGINS = set()

    # From explicit env
    _cors_env = getattr(settings, "CORS_ORIGINS", "")
    if _cors_env:
        for o in _cors_env.split(","):
            o = o.strip()
            if o:
                _CORS_ORIGINS.add(o)

    # Common env fallbacks
    for key in ("FRONTEND_URL", "NEXTAUTH_URL"):
        val = getattr(settings, key, None)
        if val:
            _CORS_ORIGINS.add(val.rstrip("/"))

    # Always allow canonical prod app
    _CORS_ORIGINS.add("https://app.fortressflow.ai")

    # Temporary: allow current Vercel frontend
    _CORS_ORIGINS.add("https://frontend-six-murex-37.vercel.app")

    _CORS_ORIGINS = list(_CORS_ORIGINS)
else:
    _CORS_ORIGINS = _DEV_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_origin_regex=r"^https://frontend-[a-z0-9-]+\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
