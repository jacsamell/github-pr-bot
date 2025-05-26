from pr_agent.config_loader import get_settings


def get_secret_provider():
    if not get_settings().get("CONFIG.SECRET_PROVIDER"):
        return None
    
    provider_id = get_settings().config.secret_provider
    if not provider_id:
        return None
    
    # No secret providers currently supported
    raise ValueError(f"Unknown SECRET_PROVIDER: {provider_id}")
