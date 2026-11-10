from scraper import parse

HTML = """
<article class="product_pod">
  <p class="star-rating Three"></p>
  <h3><a href="a-light_1000/index.html" title="A Light in the Attic">A Light...</a></h3>
  <p class="price_color">£51.77</p>
  <p class="instock availability"> In stock </p>
</article>
<li class="next"><a href="page-2.html">next</a></li>
"""


def test_parse():
    rows, next_url = parse(HTML, "https://example.com/catalogue/page-1.html")
    assert rows == [{
        "title": "A Light in the Attic",
        "price_gbp": 51.77,
        "rating": 3,
        "in_stock": True,
        "url": "https://example.com/catalogue/a-light_1000/index.html",
    }]
    assert next_url == "https://example.com/catalogue/page-2.html"
    assert parse("<html></html>", "https://example.com/")[1] is None  # last page
