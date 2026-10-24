from expense_intelligence.rate_limit import InstanceRateLimiter


def test_specific_limits_return_retry_guidance_without_storing_raw_identity():
    limiter = InstanceRateLimiter()
    for _ in range(5):
        allowed, _, _ = limiter.check("hashed-user", "/v1/agent/chat", "POST", now=120)
        assert allowed
    allowed, remaining, retry_after = limiter.check("hashed-user", "/v1/agent/chat", "POST", now=120)
    assert not allowed
    assert remaining == 0
    assert retry_after == 60
    assert all("Bearer" not in key[0] for key in limiter._counts)


def test_rate_limits_are_isolated_by_hashed_caller_and_window():
    limiter = InstanceRateLimiter()
    for _ in range(5):
        limiter.check("first", "/v1/agent/chat", "POST", now=179)
    assert limiter.check("second", "/v1/agent/chat", "POST", now=179)[0]
    assert limiter.check("first", "/v1/agent/chat", "POST", now=180)[0]
