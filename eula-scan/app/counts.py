import model
print(dict(model._ex("select count(*) policies from  tos_text").fetchone()))
print(dict(model._ex("select count(*) companies from company where last_error is null").fetchone()))

