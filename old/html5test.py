import html5lib
f = open("index.html")
parser = html5lib.HTMLParser()
document = parser.parse(f)