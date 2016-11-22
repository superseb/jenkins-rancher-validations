#
class rancher_infra(
  Pattern[/^[a-z]{2}\-[a-z]+\-\d+$/]  $region = 'us-west-2',
  Pattern[/^[a-e]$/]                  $zone = 'a',
  ) {
}
