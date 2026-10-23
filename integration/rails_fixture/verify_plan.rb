require 'json'
require_relative 'config/environment'
require 'rack/mock'

plan = JSON.parse(File.read(ARGV.fetch(0)))
request = Rack::MockRequest.new(Rails.application)
results = plan.fetch('candidates').map do |candidate|
  path = candidate.fetch('path')
  response = request.get(path, 'HTTP_HOST' => 'www.example.com')
  recognized = Rails.application.routes.recognize_path(path, method: :get)
  target = "#{recognized.fetch(:controller)}##{recognized.fetch(:action)}"
  expected = candidate.fetch('reasons').filter_map { |reason| reason['route'] }.uniq
  warned = plan.fetch('review_notes').any? do |note|
    note['path'] == path && note['earlier_target'] == target
  end
  raise "Non-200 fixture response: #{path}: #{response.status}" unless response.status == 200
  raise "Missing fixture HTML: #{path}" unless response.body.include?('Fixture ')
  raise "Unwarned dispatch mismatch: #{path}: #{target}" unless expected.include?(target) || warned
  { path: path, status: response.status, actual_target: target,
    candidate_targets: expected, dispatch_matches_candidate: expected.include?(target),
    mismatch_in_review_notes: warned, fixture_html_rendered: true }
end
puts JSON.pretty_generate(ruby: RUBY_VERSION, rails: Rails.version,
                          method: 'in-process Rack::MockRequest; no browser or network server',
                          screenshots_captured: false, results: results)
