package normalized

import "testing"

func TestTextShapes(t *testing.T) {
	cases := map[string]any{
		"plain":  " plain ",
		"single": Object{"text": "single"},
		"nested": Object{"text": Object{"text": "nested", "attributes": []any{}}},
	}
	for want, value := range cases {
		if got := Text(value); got != want {
			t.Errorf("Text(%v) = %q, want %q", value, got, want)
		}
	}
	for _, value := range []any{nil, 3.0, Object{}, Object{"text": 1.0}} {
		if got := Text(value); got != "" {
			t.Errorf("Text(%v) = %q, want empty", value, got)
		}
	}
}

func TestReferencesAndHelpers(t *testing.T) {
	doc := Parse([]byte(`{
		"data": {"*elements": ["urn:a", "urn:missing"], "inline": {"x": 1}, "*one": "urn:b"},
		"included": [
			{"entityUrn": "urn:a", "$type": "com.linkedin.Foo", "n": 3, "f": 1.5},
			{"entityUrn": "urn:b", "$type": "com.linkedin.Bar"},
			"not an object"
		]
	}`))
	if len(doc.Included) != 2 {
		t.Fatalf("included = %v", doc.Included)
	}
	if doc.Ref(doc.Data, "inline")["x"] != 1.0 || doc.Ref(doc.Data, "one")["entityUrn"] != "urn:b" {
		t.Error("Ref did not resolve inline or referenced entities")
	}
	if refs := doc.Refs(doc.Data, "elements"); len(refs) != 1 || refs[0]["entityUrn"] != "urn:a" {
		t.Errorf("Refs = %v", refs)
	}
	if len(doc.OfType("Foo")) != 1 || doc.Ref(nil, "x") != nil {
		t.Error("OfType or nil handling failed")
	}
	a := doc.Get("urn:a")
	if n, ok := Int(a["n"]); !ok || n != 3 {
		t.Error("Int failed on a whole number")
	}
	if _, ok := Int(a["f"]); ok {
		t.Error("Int accepted a fraction")
	}
	if Dig(doc.Data, "inline", "x") != 1.0 || Dig(doc.Data, "inline", "x", "y") != nil {
		t.Error("Dig failed")
	}
}
