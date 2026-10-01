// Package normalized reads Voyager's "normalized" JSON format.
//
// With `accept: application/vnd.linkedin.normalized+json+2.1`, responses are
//
//	{"data": {...}, "included": [{"entityUrn": "urn:li:...", "$type": "...", ...}, ...]}
//
// and entities reference each other by URN through keys prefixed with "*",
// e.g. {"*socialDetail": "urn:li:fs_socialDetail:..."}. Shapes are
// undocumented and change, so every accessor tolerates missing data.
package normalized

import (
	"encoding/json"
	"strings"
)

// Object is a decoded JSON object.
type Object = map[string]any

// Doc is a parsed normalized response.
type Doc struct {
	Data     Object
	Included []Object
	byURN    map[string]Object
}

// Parse decodes a response. Anything that is not a normalized document gives an empty Doc.
func Parse(raw []byte) *Doc {
	var payload Object
	_ = json.Unmarshal(raw, &payload)
	return FromObject(payload)
}

// FromObject builds a Doc from an already decoded response.
func FromObject(payload Object) *Doc {
	doc := &Doc{Data: Object{}, byURN: map[string]Object{}}
	if data, ok := payload["data"].(Object); ok {
		doc.Data = data
	}
	if included, ok := payload["included"].([]any); ok {
		for _, item := range included {
			if entity, ok := item.(Object); ok {
				doc.Included = append(doc.Included, entity)
				if urn, ok := entity["entityUrn"].(string); ok {
					doc.byURN[urn] = entity
				}
			}
		}
	}
	return doc
}

// Get returns the included entity with this URN.
func (d *Doc) Get(urn any) Object {
	if s, ok := urn.(string); ok {
		return d.byURN[s]
	}
	return nil
}

// Ref returns obj[key] if inlined, otherwise resolves the "*key" URN reference.
func (d *Doc) Ref(obj Object, key string) Object {
	if obj == nil {
		return nil
	}
	if inline, ok := obj[key].(Object); ok {
		return inline
	}
	return d.Get(obj["*"+key])
}

// Refs is Ref for lists of entities.
func (d *Doc) Refs(obj Object, key string) []Object {
	if obj == nil {
		return nil
	}
	var out []Object
	if inline, ok := obj[key].([]any); ok {
		for _, item := range inline {
			if entity, ok := item.(Object); ok {
				out = append(out, entity)
			}
		}
		return out
	}
	if urns, ok := obj["*"+key].([]any); ok {
		for _, urn := range urns {
			if entity := d.Get(urn); entity != nil {
				out = append(out, entity)
			}
		}
	}
	return out
}

// OfType returns the included entities whose $type ends with the suffix.
func (d *Doc) OfType(suffix string) []Object {
	var out []Object
	for _, entity := range d.Included {
		if t, _ := entity["$type"].(string); strings.HasSuffix(t, suffix) {
			out = append(out, entity)
		}
	}
	return out
}

// Text extracts text from LinkedIn's TextViewModel shapes:
// "x", {"text": "x"} or {"text": {"text": "x"}}.
func Text(value any) string {
	for range 5 {
		switch v := value.(type) {
		case string:
			return strings.TrimSpace(v)
		case Object:
			value = v["text"]
		default:
			return ""
		}
	}
	return ""
}

// Dig follows nested object keys.
func Dig(value any, keys ...string) any {
	for _, key := range keys {
		obj, ok := value.(Object)
		if !ok {
			return nil
		}
		value = obj[key]
	}
	return value
}

// String returns value if it is a string.
func String(value any) string {
	s, _ := value.(string)
	return s
}

// Int returns value as an int if it is a whole JSON number.
func Int(value any) (int, bool) {
	f, ok := value.(float64)
	if !ok || f != float64(int(f)) {
		return 0, false
	}
	return int(f), true
}
