require 'rails'
require 'action_controller/railtie'

# A real mounted-engine appendix exercises a format synthetic fixtures missed.
module Embedded
  class Engine < Rails::Engine
    isolate_namespace Embedded
    config.root = File.expand_path('../embedded', __dir__)
  end
end

# Self-authored routing fixture: no upstream app code, database, or external calls.
module RouteSnapFixture
  class Application < Rails::Application
    config.eager_load = false
    config.secret_key_base = 'local-routing-fixture-not-a-production-secret'
    config.hosts = ['www.example.com', '127.0.0.1', 'localhost']
    config.logger = Logger.new(File::NULL)
  end
end
