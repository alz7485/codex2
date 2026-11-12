"""Compare macro attributes by meaning after canonical E3D spelling changes."""
from catalog_studio import expressions
from catalog_studio.editor_rules import defaults

def assert_attrs_equivalent(case,old,new,kind):
    from catalog_studio import element_schema as schema
    if kind in schema.GM_TYPES:old=dict(old,NAPP='0')
    case.assertTrue(set(new)<=set(old),str(set(new)-set(old)))
    for key,value in old.items():
        if key not in new:
            case.assertEqual(str(value).casefold(),str(defaults(kind).get(key,'<not-default>')).casefold())
        elif new[key]!=value:
            if str(value).lower() in ('','unset'):case.assertEqual(new[key],'')
            else:case.assertEqual(expressions.parse(value),expressions.parse(new[key]))
