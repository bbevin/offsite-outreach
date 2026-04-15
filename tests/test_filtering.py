"""Tests for input pre-filtering in classifier.should_skip_url."""
from classifier import should_skip_url


class TestSocialFiltering:
    def test_reddit_root(self):
        skip, reason = should_skip_url("https://reddit.com/r/recruiting")
        assert skip and reason == "social"

    def test_reddit_www(self):
        skip, reason = should_skip_url("https://www.reddit.com/r/recruiting/comments/abc")
        assert skip and reason == "social"

    def test_youtube(self):
        skip, reason = should_skip_url("https://youtube.com/watch?v=xyz")
        assert skip and reason == "social"

    def test_linkedin_subdomain(self):
        skip, reason = should_skip_url("https://business.linkedin.com/talent-solutions")
        assert skip and reason == "social"

    def test_no_scheme_input(self):
        # juicebox CSV format strips the scheme
        skip, reason = should_skip_url("reddit.com/r/recruiting")
        assert skip and reason == "social"


class TestEcommerceFiltering:
    def test_amazon(self):
        skip, reason = should_skip_url("https://amazon.com/dp/B07XYZ")
        assert skip and reason == "ecommerce"

    def test_walmart(self):
        skip, reason = should_skip_url("https://www.walmart.com/ip/some-product/123")
        assert skip and reason == "ecommerce"

    def test_target_subdomain(self):
        skip, reason = should_skip_url("https://intl.target.com/p/foo")
        assert skip and reason == "ecommerce"


class TestLandingPageFiltering:
    def test_bare_domain(self):
        skip, reason = should_skip_url("https://example.com")
        assert skip and reason == "landing_page"

    def test_bare_domain_trailing_slash(self):
        skip, reason = should_skip_url("https://example.com/")
        assert skip and reason == "landing_page"

    def test_subdomain_bare(self):
        skip, reason = should_skip_url("https://blog.example.com/")
        assert skip and reason == "landing_page"

    def test_query_string_only(self):
        skip, reason = should_skip_url("https://example.com/?utm_source=foo")
        assert skip and reason == "landing_page"


class TestNonSkipped:
    def test_blog_post(self):
        skip, reason = should_skip_url("https://example.com/blog/best-ai-recruiting-tools")
        assert not skip and reason == ""

    def test_vendor_subpath(self):
        skip, reason = should_skip_url("https://juicebox.ai/blog/ai-recruiting-tools")
        assert not skip and reason == ""

    def test_techradar_article(self):
        # affiliate site but not in skip lists — should pass through to classifier
        skip, reason = should_skip_url("https://techradar.com/best/recruitment-platforms")
        assert not skip and reason == ""


class TestPrecedence:
    def test_social_beats_landing(self):
        # reddit.com root is both social AND landing-page-shaped — social wins
        skip, reason = should_skip_url("https://reddit.com/")
        assert skip and reason == "social"
