package api

import (
	"context"
	"regexp"
	"strings"
)

// PublishedPost identifies a post created by Publish.
type PublishedPost struct {
	URN string `json:"urn,omitempty"`
	URL string `json:"url,omitempty"`
}

// Visibility controls who can see a new post.
type Visibility int

const (
	// Anyone makes the post public.
	Anyone Visibility = iota
	// ConnectionsOnly limits the post to your connections.
	ConnectionsOnly
)

// SharePayload builds the body LinkedIn's web app sends to create a text post.
func SharePayload(text string, visibility Visibility) map[string]any {
	return map[string]any{
		"visibleToConnectionsOnly":  visibility == ConnectionsOnly,
		"externalAudienceProviders": []any{},
		"commentaryV2": map[string]any{
			"text":       text,
			"attributes": []any{},
		},
		"origin":                 "FEED",
		"allowedCommentersScope": "ALL",
		"postState":              "PUBLISHED",
		"media":                  []any{},
	}
}

// Publish creates a text post. The caller is responsible for getting the
// user's confirmation first.
func Publish(ctx context.Context, c Client, text string, visibility Visibility) (PublishedPost, error) {
	raw, err := c.Post(ctx, "/contentcreation/normShares", nil, SharePayload(text, visibility))
	if err != nil {
		return PublishedPost{}, err
	}
	return ParsePublished(raw), nil
}

var postURN = regexp.MustCompile(`urn:li:(?:activity|share|ugcPost):\d+`)

// ParsePublished finds the new post's URN in the response, wherever it is.
func ParsePublished(raw []byte) PublishedPost {
	var post PublishedPost
	for _, match := range postURN.FindAllString(string(raw), -1) {
		// The activity URN is the one that works in /feed/update/ links.
		if post.URN == "" || strings.HasPrefix(match, "urn:li:activity:") {
			post.URN = match
		}
	}
	if post.URN != "" {
		post.URL = "https://www.linkedin.com/feed/update/" + post.URN + "/"
	}
	return post
}
