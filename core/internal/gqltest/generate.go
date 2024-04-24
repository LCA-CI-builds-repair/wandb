p// Generate mock for Client interface
//go:generate mockgen -destination gqltest_gen.go -package gqltest github.com/Khan/genqlient/graphql Clientkage gqltest

//go:generate mockgen -destination gqltest_gen.go -package gqltest github.com/Khan/genqlient/graphql Client
