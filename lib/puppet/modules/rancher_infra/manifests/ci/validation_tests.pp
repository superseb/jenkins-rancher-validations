#
class rancher_infra::ci::validation_tests(
  Pattern[/^[a-z]{2}\-[a-z]+\-\d+$/]            $region          = $::rancher_infra::region,
  Pattern[/^[a-e]$/]                            $zone            = $::rancher_infra::zone,
  Hash[String, String]                          $default_tags    = { 'is_ci' => 'true' },
  ) {
  require ::rancher_infra::ci
}
