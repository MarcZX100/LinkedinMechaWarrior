package cli

import (
	"strings"

	"github.com/spf13/cobra"

	"github.com/MarcZX100/LinkedinMechaWarrior/internal/api"
	"github.com/MarcZX100/LinkedinMechaWarrior/internal/errs"
	"github.com/MarcZX100/LinkedinMechaWarrior/internal/output"
	"github.com/MarcZX100/LinkedinMechaWarrior/internal/voyager"
)

func (a *app) meCommand() *cobra.Command {
	return &cobra.Command{
		Use:   "me",
		Short: "Show your profile",
		Args:  exactArgs(0, "no arguments"),
		RunE: func(cmd *cobra.Command, _ []string) error {
			var profile api.Profile
			err := a.withClient(func(c *voyager.Client) (err error) {
				profile, err = api.Me(cmd.Context(), c)
				return err
			})
			if err != nil {
				return err
			}
			if a.jsonOut {
				return output.JSON(a.stdout, profile)
			}
			a.printf("%s\n", output.Profile(profile))
			return nil
		},
	}
}

func (a *app) feedCommand() *cobra.Command {
	var limit int
	var full bool
	cmd := &cobra.Command{
		Use:   "feed",
		Short: "Show your home feed",
		Args:  exactArgs(0, "no arguments"),
		RunE: func(cmd *cobra.Command, _ []string) error {
			if limit < 1 || limit > api.MaxFeedPosts {
				return errs.New(errs.Usage, "--limit must be between 1 and %d", api.MaxFeedPosts)
			}
			var posts []api.FeedPost
			err := a.withClient(func(c *voyager.Client) (err error) {
				posts, err = api.Feed(cmd.Context(), c, limit)
				return err
			})
			if err != nil {
				return err
			}
			if a.jsonOut {
				if posts == nil {
					posts = []api.FeedPost{}
				}
				return output.JSON(a.stdout, posts)
			}
			if len(posts) == 0 {
				a.printf("No posts found. If your feed is not empty, LinkedIn may have changed its API; see `lmw har --help`.\n")
				return nil
			}
			formatted := make([]string, len(posts))
			for i, p := range posts {
				formatted[i] = output.FeedPost(p, full)
			}
			a.printf("%s\n", strings.Join(formatted, "\n\n"))
			return nil
		},
	}
	cmd.Flags().IntVarP(&limit, "limit", "n", 10, "number of posts (1-50)")
	cmd.Flags().BoolVar(&full, "full", false, "show complete post texts")
	return cmd
}
